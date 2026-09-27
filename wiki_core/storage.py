"""Implementazione dello storage del wiki su filesystem.

Convenzioni:
- Una pagina è un file con estensione ``.md`` o ``.html``.
- I percorsi forniti dall'esterno sono *relativi* alla root del wiki
  e usano il separatore ``/``.
- Tutti i percorsi vengono risolti e validati per impedire traversal.
- I file binari (asset) non sono gestiti da questo modulo.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import unicodedata
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

VALID_EXTENSIONS = {".md", ".markdown", ".html", ".htm"}
MAX_PATH_PARTS = 32
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB, limite di sicurezza per le pagine
DEFAULT_WRITE_LOCK_TIMEOUT = 10.0
LOCK_FILE_NAME = ".wiki-kiss.lock"

_THREAD_LOCKS: dict[Path, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class WikiStorageError(Exception):
    """Errore generico dello storage."""


class InvalidPathError(WikiStorageError):
    """Il percorso fornito non è valido o tenta un traversal."""


class PageNotFoundError(WikiStorageError):
    """La pagina richiesta non esiste."""


class PageAlreadyExistsError(WikiStorageError):
    """La pagina esiste già e ``overwrite`` è False."""


class WriteLockTimeoutError(WikiStorageError):
    """Il lock esclusivo del wiki non è stato acquisito entro il timeout."""


@dataclass(frozen=True)
class PageInfo:
    """Metadati di una pagina."""

    path: str
    title: str
    size: int
    modified: float
    extension: str


@dataclass(frozen=True)
class SearchResult:
    """Singola occorrenza restituita da :meth:`WikiStorage.search`."""

    path: str
    line_number: int
    line: str
    matches: int = 1
    snippet: str = ""


class WikiStorage:
    """Wrapper filesystem-oriented per il wiki.

    Parameters
    ----------
    root:
        Cartella radice del wiki. Deve esistere.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        write_lock_timeout: float = DEFAULT_WRITE_LOCK_TIMEOUT,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise WikiStorageError(
                f"La cartella wiki non esiste: {self.root}"
            )
        if not self.root.is_dir():
            raise WikiStorageError(
                f"Il percorso wiki non è una cartella: {self.root}"
            )
        if write_lock_timeout < 0:
            raise WikiStorageError("Il timeout del lock non può essere negativo.")
        self.write_lock_timeout = float(write_lock_timeout)
        with _THREAD_LOCKS_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(self.root, threading.RLock())

    # ------------------------------------------------------------------
    # Utilità
    # ------------------------------------------------------------------

    def _normalize_path(self, raw: str) -> str:
        """Normalizza un percorso relativo fornito dall'esterno.

        - Rimuove slash iniziali/finali.
        - Vietati ``..`` e percorsi assoluti.
        - Vietati caratteri di controllo e NUL.
        """
        if raw is None:
            raise InvalidPathError("Percorso nullo.")
        if not isinstance(raw, str):
            raise InvalidPathError("Il percorso deve essere una stringa.")
        if "\x00" in raw:
            raise InvalidPathError("Percorso con carattere NUL.")
        cleaned = raw.strip().replace("\\", "/")
        if cleaned.startswith("/"):
            cleaned = cleaned.lstrip("/")
        if cleaned == "":
            raise InvalidPathError("Percorso vuoto.")
        parts = [p for p in cleaned.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise InvalidPathError("Percorso non valido: contiene '..'.")
        if any(control in p for p in parts for control in ("\n", "\r", "\t")):
            raise InvalidPathError("Percorso con caratteri di controllo.")
        if len(parts) > MAX_PATH_PARTS:
            raise InvalidPathError("Percorso troppo profondo.")
        return "/".join(parts)

    def _resolve(self, rel_path: str) -> Path:
        rel = self._normalize_path(rel_path)
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:  # pragma: no cover - difesa
            raise InvalidPathError("Percorso fuori dalla root del wiki.") from exc
        return candidate

    @staticmethod
    def _title_from_path(rel_path: str, content: str | None = None) -> str:
        """Ricava un titolo leggibile dal percorso o dal contenuto."""
        if content is not None:
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
        name = rel_path.rsplit("/", 1)[-1]
        stem = Path(name).stem
        return stem.replace("-", " ").replace("_", " ").strip() or rel_path

    @staticmethod
    def _slugify(text: str) -> str:
        """Slug semplice per il default di una nota."""
        normalized = unicodedata.normalize("NFKD", text)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_only).strip().lower()
        slug = re.sub(r"[\s_-]+", "-", slug)
        return slug.strip("-") or "nota"

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        """Serializza le mutazioni della stessa root tra thread e processi.

        Il file di lock resta nella root ed è ignorato dalle API del wiki.
        Il lock del sistema operativo viene rilasciato automaticamente anche
        se il processo termina; non esistono quindi lock obsoleti da pulire.
        """
        deadline = time.monotonic() + self.write_lock_timeout
        acquired_thread = self._thread_lock.acquire(timeout=self.write_lock_timeout)
        if not acquired_thread:
            raise WriteLockTimeoutError(
                "Timeout in attesa del lock di scrittura del wiki."
            )

        lock_handle = None
        process_lock_acquired = False
        try:
            lock_path = self.root / LOCK_FILE_NAME
            lock_handle = lock_path.open("a+b")
            if os.name == "nt":
                lock_handle.seek(0, os.SEEK_END)
                if lock_handle.tell() == 0:
                    lock_handle.write(b"\0")
                    lock_handle.flush()

            while True:
                try:
                    self._acquire_process_lock(lock_handle)
                    process_lock_acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise WriteLockTimeoutError(
                            "Timeout in attesa del lock di scrittura del wiki."
                        ) from None
                    time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
            yield
        finally:
            if lock_handle is not None:
                if process_lock_acquired:
                    self._release_process_lock(lock_handle)
                lock_handle.close()
            self._thread_lock.release()

    @staticmethod
    def _acquire_process_lock(lock_handle) -> None:
        if os.name == "nt":  # pragma: no cover - eseguito su Windows
            import errno
            import msvcrt

            lock_handle.seek(0)
            try:
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN):
                    raise BlockingIOError from exc
                raise
            return

        import fcntl

        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _release_process_lock(lock_handle) -> None:
        if os.name == "nt":  # pragma: no cover - eseguito su Windows
            import msvcrt

            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _atomic_write_text(target: Path, content: str) -> None:
        """Scrive un file completo senza esporre contenuti parziali ai lettori."""
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            if target.exists():
                os.chmod(temporary_path, target.stat().st_mode)
            else:
                os.chmod(temporary_path, 0o644)
            os.replace(temporary_path, target)
            temporary_path = None

            # Rende durevole anche il rename dove il sistema lo supporta.
            try:
                directory_fd = os.open(target.parent, os.O_RDONLY)
            except OSError:  # pragma: no cover - dipende dal filesystem
                return
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def list_pages(self, subdir: str | None = None) -> list[PageInfo]:
        """Elenca tutte le pagine del wiki, opzionalmente in una sottocartella."""
        base = self.root
        if subdir:
            base = self._resolve(subdir)
            if not base.is_dir():
                return []
        results: list[PageInfo] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in VALID_EXTENSIONS:
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                stat = path.stat()
            except OSError:
                continue
            results.append(
                PageInfo(
                    path=rel,
                    title=self._title_from_path(rel),
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    extension=ext,
                )
            )
        return results

    def read_page(self, rel_path: str) -> str:
        """Restituisce il contenuto testuale di una pagina."""
        path = self._resolve(rel_path)
        if not path.exists() or not path.is_file():
            raise PageNotFoundError(f"Pagina non trovata: {rel_path}")
        if path.suffix.lower() not in VALID_EXTENSIONS:
            raise InvalidPathError(
                f"Estensione non supportata: {path.suffix}"
            )
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise WikiStorageError(
                f"Pagina troppo grande ({size} byte): {rel_path}"
            )
        return path.read_text(encoding="utf-8")

    def page_exists(self, rel_path: str) -> bool:
        try:
            return self._resolve(rel_path).is_file()
        except InvalidPathError:
            return False

    def write_page(
        self,
        rel_path: str,
        content: str,
        overwrite: bool = True,
    ) -> PageInfo:
        """Crea o sovrascrive una pagina.

        ``rel_path`` deve terminare con un'estensione supportata; se manca
        viene aggiunto automaticamente ``.md``.
        """
        if not isinstance(content, str):
            raise WikiStorageError("Il contenuto deve essere una stringa.")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise WikiStorageError(
                "Contenuto troppo grande (max 2 MiB)."
            )
        normalized = self._normalize_path(rel_path)
        target = self._resolve(normalized)
        if target.suffix.lower() not in VALID_EXTENSIONS:
            target = target.with_suffix(".md")
            normalized = target.relative_to(self.root).as_posix()

        with self._write_lock():
            if target.exists() and not overwrite:
                raise PageAlreadyExistsError(
                    f"La pagina esiste già: {normalized}"
                )
            self._atomic_write_text(target, content)
            self._rebuild_indexes_unlocked()
            stat = target.stat()
            return PageInfo(
                path=normalized,
                title=self._title_from_path(normalized, content),
                size=stat.st_size,
                modified=stat.st_mtime,
                extension=target.suffix.lower(),
            )

    def append_note(
        self,
        content: str,
        rel_path: str | None = None,
        heading: str | None = None,
    ) -> PageInfo:
        """Aggiunge contenuto a una pagina esistente o ne crea una di log.

        Se ``rel_path`` è ``None`` o vuoto, viene creato/aggiornato il file
        di log del giorno corrente in ``wiki/logs/YYYY-MM-DD.md``.
        """
        if not content or not content.strip():
            raise WikiStorageError("Contenuto della nota vuoto.")
        if rel_path:
            normalized = self._normalize_path(rel_path)
            target = self._resolve(normalized)
            if target.suffix.lower() not in VALID_EXTENSIONS:
                target = target.with_suffix(".md")
                normalized = target.relative_to(self.root).as_posix()
        else:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            normalized = f"logs/{today}.md"
            target = self._resolve(normalized)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        block_parts: list[str] = []
        if heading:
            block_parts.append(f"## {heading.strip()}")
        block_parts.append(f"- _{timestamp}_")
        block_parts.append("")
        block_parts.append(content.rstrip())
        block = "\n".join(block_parts) + "\n"

        with self._write_lock():
            if target.exists():
                current = target.read_text(encoding="utf-8")
                merged = current + "\n" + block
            else:
                header = f"# {self._title_from_path(normalized)}\n\n"
                merged = header + block
            if len(merged.encode("utf-8")) > MAX_FILE_BYTES:
                raise WikiStorageError("Contenuto troppo grande (max 2 MiB).")
            self._atomic_write_text(target, merged)
            self._rebuild_indexes_unlocked()
            stat = target.stat()
            return PageInfo(
                path=normalized,
                title=self._title_from_path(normalized, merged),
                size=stat.st_size,
                modified=stat.st_mtime,
                extension=target.suffix.lower(),
            )

    def rebuild_indexes(self) -> None:
        """Rigenera gli indici sotto lo stesso lock usato dalle scritture."""
        with self._write_lock():
            self._rebuild_indexes_unlocked()

    def _rebuild_indexes_unlocked(self) -> None:
        """Rigenera indice generale e indici top-level; richiede il write lock."""
        categories = sorted(
            path for path in self.root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )

        # Indice generale: categorie e pagine che si trovano direttamente
        # nella root. Gli index.md generati non vengono indicizzati.
        lines = ["# Indice del Wiki", "", "## Categorie", ""]
        if categories:
            for category in categories:
                lines.append(f"- [{category.name}]({category.name}/index.md)")
        else:
            lines.append("Nessuna categoria.")
        root_pages = [
            path for path in sorted(self.root.iterdir())
            if path.is_file()
            and path.suffix.lower() in VALID_EXTENSIONS
            and path.name.lower() != "index.md"
        ]
        if root_pages:
            lines.extend(["", "## Pagine", ""])
            for page in root_pages:
                title = self._title_from_path(page.name, page.read_text(encoding="utf-8"))
                lines.append(f"- [{title}]({page.name})")
        self._atomic_write_text(self.root / "index.md", "\n".join(lines) + "\n")

        for category in categories:
            index_path = category / "index.md"
            pages = [
                path for path in sorted(category.rglob("*"))
                if path.is_file()
                and path.suffix.lower() in VALID_EXTENSIONS
                and path.name.lower() != "index.md"
            ]
            category_lines = [f"# {category.name}"]
            if pages:
                category_lines.append("")
            for page in pages:
                title = self._title_from_path(
                    page.relative_to(self.root).as_posix(),
                    page.read_text(encoding="utf-8"),
                )
                link = Path(os.path.relpath(page, category)).as_posix()
                category_lines.append(f"- [{title}]({link})")
            self._atomic_write_text(index_path, "\n".join(category_lines) + "\n")

    def search(
        self,
        query: str,
        subdir: str | None = None,
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> list[SearchResult]:
        """Ricerca full-text semplice.

        Scandisce ricorsivamente la root (o ``subdir``) e restituisce fino a
        ``max_results`` occorrenze, ordinate per percorso e numero di riga.
        """
        if not query or not query.strip():
            return []
        if max_results <= 0:
            max_results = 50
        needle = query if case_sensitive else query.lower()
        results: list[SearchResult] = []
        for path in self._iter_files(subdir):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                hay_line = line if case_sensitive else line.lower()
                count = hay_line.count(needle)
                if count == 0:
                    continue
                results.append(
                    SearchResult(
                        path=path.relative_to(self.root).as_posix(),
                        line_number=line_no,
                        line=line.strip()[:400],
                        matches=count,
                        snippet=self._make_snippet(line, needle, case_sensitive),
                    )
                )
                if len(results) >= max_results:
                    return results
        return results

    # ------------------------------------------------------------------
    # Helpers interni
    # ------------------------------------------------------------------

    def _iter_files(self, subdir: str | None) -> Iterable[Path]:
        base = self.root
        if subdir:
            base = self._resolve(subdir)
            if not base.is_dir():
                return iter(())
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS:
                yield path

    @staticmethod
    def _make_snippet(
        line: str,
        needle: str,
        case_sensitive: bool,
        width: int = 120,
    ) -> str:
        hay = line if case_sensitive else line.lower()
        idx = hay.find(needle)
        if idx < 0:
            return line[:width]
        start = max(0, idx - 30)
        end = min(len(line), idx + len(needle) + 60)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(line) else ""
        return f"{prefix}{line[start:end].strip()}{suffix}"

    # ------------------------------------------------------------------
    # Introspezione
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        pages = self.list_pages()
        total_size = sum(p.size for p in pages)
        return {
            "pages": len(pages),
            "total_bytes": total_size,
            "extensions": self._count_by_ext(pages),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _count_by_ext(pages: Iterable[PageInfo]) -> dict:
        counts: dict = {}
        for page in pages:
            counts[page.extension] = counts.get(page.extension, 0) + 1
        return counts
