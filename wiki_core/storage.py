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
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

VALID_EXTENSIONS = {".md", ".markdown", ".html", ".htm"}
MAX_PATH_PARTS = 32
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB, limite di sicurezza per le pagine


class WikiStorageError(Exception):
    """Errore generico dello storage."""


class InvalidPathError(WikiStorageError):
    """Il percorso fornito non è valido o tenta un traversal."""


class PageNotFoundError(WikiStorageError):
    """La pagina richiesta non esiste."""


class PageAlreadyExistsError(WikiStorageError):
    """La pagina esiste già e ``overwrite`` è False."""


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

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise WikiStorageError(
                f"La cartella wiki non esiste: {self.root}"
            )
        if not self.root.is_dir():
            raise WikiStorageError(
                f"Il percorso wiki non è una cartella: {self.root}"
            )

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
    def _title_from_path(rel_path: str, content: Optional[str] = None) -> str:
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

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def list_pages(self, subdir: Optional[str] = None) -> List[PageInfo]:
        """Elenca tutte le pagine del wiki, opzionalmente in una sottocartella."""
        base = self.root
        if subdir:
            base = self._resolve(subdir)
            if not base.is_dir():
                return []
        results: List[PageInfo] = []
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
        if target.exists() and not overwrite:
            raise PageAlreadyExistsError(
                f"La pagina esiste già: {normalized}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
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
        rel_path: Optional[str] = None,
        heading: Optional[str] = None,
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

        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            header = f"# {self._title_from_path(normalized)}\n\n"
        else:
            header = ""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        block_parts: List[str] = []
        if heading:
            block_parts.append(f"## {heading.strip()}")
        block_parts.append(f"- _{timestamp}_")
        block_parts.append("")
        block_parts.append(content.rstrip())
        block = "\n".join(block_parts) + "\n"
        mode = "a" if target.exists() else "w"
        with target.open(mode, encoding="utf-8") as fh:
            if mode == "w":
                fh.write(header)
            fh.write("\n" + block if mode == "a" else block)
        stat = target.stat()
        merged = target.read_text(encoding="utf-8")
        return PageInfo(
            path=normalized,
            title=self._title_from_path(normalized, merged),
            size=stat.st_size,
            modified=stat.st_mtime,
            extension=target.suffix.lower(),
        )

    def search(
        self,
        query: str,
        subdir: Optional[str] = None,
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> List[SearchResult]:
        """Ricerca full-text semplice.

        Scandisce ricorsivamente la root (o ``subdir``) e restituisce fino a
        ``max_results`` occorrenze, ordinate per percorso e numero di riga.
        """
        if not query or not query.strip():
            return []
        if max_results <= 0:
            max_results = 50
        needle = query if case_sensitive else query.lower()
        results: List[SearchResult] = []
        for path in self._iter_files(subdir):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            haystack = text if case_sensitive else text.lower()
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

    def _iter_files(self, subdir: Optional[str]) -> Iterable[Path]:
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
            "root": str(self.root),
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
