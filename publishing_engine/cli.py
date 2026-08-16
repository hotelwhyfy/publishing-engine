"""Command line: ``publish build``, ``publish list``, ``publish new``."""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from . import __version__, builder, config, templates

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "examples", "sample-book")


def _list(args):
    found = config.discover(args.root)
    if not found:
        print(f"no books under {args.root} "
              f"(looked for {' or '.join(config.CONFIG_NAMES)})")
        return 1
    for directory in found:
        book = config.load(directory)
        rel = os.path.relpath(directory, args.root)
        print(f"  {book.slug:<24} {book.template:<7} {book.title:<32} {rel}")
    return 0


def _build(args):
    found = config.discover(args.root)
    if not found:
        print(f"no books under {args.root}", file=sys.stderr)
        return 1

    selected = []
    for directory in found:
        book = config.load(directory)
        if not args.book or any(s == book.slug or s in directory for s in args.book):
            selected.append(directory)
    if not selected:
        print(f"nothing matches {args.book} (try: publish list)", file=sys.stderr)
        return 1

    for directory in selected:
        result = builder.build(directory, covers=not args.no_covers, html=not args.no_html)
        print(f"\n=== {result.title} ===")
        print(f"  {len(result.pdfs)} PDF(s) ({result.page_summary()}), fonts embedded")
        if result.html:
            print(f"  {os.path.basename(result.html)}")
    print("\nDone.")
    return 0


def _new(args):
    target = os.path.abspath(args.directory)
    if os.path.exists(target) and os.listdir(target):
        print(f"{target} already exists and is not empty", file=sys.stderr)
        return 1
    shutil.copytree(EXAMPLE, target, dirs_exist_ok=True)
    shutil.rmtree(os.path.join(target, "dist"), ignore_errors=True)
    print(f"created {target}\nEdit book.toml and content.md, then: publish build {target}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="publish",
        description="Build print-ready book interiors, covers and reading HTML from a "
                    "single config file.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="build one book, several, or everything found")
    p.add_argument("book", nargs="*", help="slug or path fragment; omit to build all")
    p.add_argument("--root", default=".", help="where to look for books (default: .)")
    p.add_argument("--no-covers", action="store_true", help="skip cover wraps")
    p.add_argument("--no-html", action="store_true", help="skip reading HTML")
    p.set_defaults(func=_build)

    p = sub.add_parser("list", help="list the books found")
    p.add_argument("--root", default=".")
    p.set_defaults(func=_list)

    p = sub.add_parser("new", help="start a book from the example")
    p.add_argument("directory")
    p.set_defaults(func=_new)

    p = sub.add_parser("templates", help="list the available templates")
    p.set_defaults(func=lambda a: (print("\n".join(f"  {n}" for n in templates.names())), 0)[1])

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
