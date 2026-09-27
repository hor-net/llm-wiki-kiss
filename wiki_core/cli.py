"""CLI locale per leggere e modificare un singolo wiki senza rete."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .storage import WikiStorage, WikiStorageError

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "wiki"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki-kiss",
        description="Offline local access to a single KISS wiki.",
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("WIKI_ROOT", str(DEFAULT_ROOT)),
        help="Wiki root (default: WIKI_ROOT or ./wiki).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_command = commands.add_parser("list", help="Lists the pages in JSON.")
    list_command.add_argument("--subdir", help="Restrict to a subfolder.")

    read_command = commands.add_parser("read", help="Prints a page to stdout.")
    read_command.add_argument("path", help="Relative path of the page.")

    search_command = commands.add_parser("search", help="Searches text across pages.")
    search_command.add_argument("query")
    search_command.add_argument("--subdir")
    search_command.add_argument("--max-results", type=int, default=50)
    search_command.add_argument("--case-sensitive", action="store_true")

    write_command = commands.add_parser("write", help="Creates or overwrites a page.")
    write_command.add_argument("path")
    _add_content_arguments(write_command)
    write_command.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Fail if the page already exists.",
    )

    append_command = commands.add_parser("append", help="Appends a note or log entry.")
    append_command.add_argument(
        "path",
        nargs="?",
        help="Target page; defaults to today's log when omitted.",
    )
    append_command.add_argument("--heading")
    _add_content_arguments(append_command)

    commands.add_parser("stats", help="Shows statistics in JSON.")
    commands.add_parser("rebuild-indexes", help="Rebuilds the wiki indexes.")
    return parser


def _add_content_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--content", help="Content passed directly.")
    source.add_argument(
        "--file",
        type=Path,
        help="Reads the content from a file; use '-' for stdin.",
    )


def _read_content(args: argparse.Namespace) -> str:
    if args.content is not None:
        return args.content
    if args.file is not None and str(args.file) != "-":
        try:
            return args.file.expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise WikiStorageError(f"Cannot read the file: {args.file}") from exc
    if sys.stdin.isatty():
        raise WikiStorageError("Provide --content, --file or content on stdin.")
    return sys.stdin.read()


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run(args: argparse.Namespace) -> None:
    storage = WikiStorage(args.root)

    if args.command == "list":
        pages = storage.list_pages(subdir=args.subdir)
        _print_json({"count": len(pages), "pages": [asdict(page) for page in pages]})
        return

    if args.command == "read":
        content = storage.read_page(args.path)
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
        return

    if args.command == "search":
        results = storage.search(
            query=args.query,
            subdir=args.subdir,
            max_results=args.max_results,
            case_sensitive=args.case_sensitive,
        )
        _print_json({
            "query": args.query,
            "count": len(results),
            "results": [
                {
                    "path": result.path,
                    "line": result.line_number,
                    "matches": result.matches,
                    "snippet": result.snippet,
                }
                for result in results
            ],
        })
        return

    if args.command == "write":
        info = storage.write_page(
            rel_path=args.path,
            content=_read_content(args),
            overwrite=not args.no_overwrite,
        )
        _print_json(asdict(info))
        return

    if args.command == "append":
        info = storage.append_note(
            content=_read_content(args),
            rel_path=args.path,
            heading=args.heading,
        )
        _print_json(asdict(info))
        return

    if args.command == "stats":
        _print_json(storage.stats())
        return

    if args.command == "rebuild-indexes":
        storage.rebuild_indexes()
        _print_json({"status": "ok"})
        return

    raise WikiStorageError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _run(args)
    except (OSError, UnicodeError, WikiStorageError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
