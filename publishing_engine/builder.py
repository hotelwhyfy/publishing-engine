"""Build one book: interiors, covers, reading HTML, listing copy.

Everything lands in the book's ``dist/`` directory. Scratch rasters go to a subdirectory
that is deleted on the way out, so ``dist/`` holds only finished artefacts.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from . import config, cover, numbers, pdftools, templates


@dataclass
class Result:
    """What a build produced."""

    slug: str
    title: str
    template: str
    pages: dict = field(default_factory=dict)
    pdfs: list = field(default_factory=list)
    html: str = ""
    description: str = ""

    def page_summary(self) -> str:
        return ", ".join(f"{name} {count} pp" for name, count in self.pages.items())


def listing_text(book) -> str:
    """The plain-text catalogue entry: identification, then the book's own copy."""
    head = [book.title.upper()]
    if book.series_label:
        line = book.series_label
        if book.volume:
            line += f" · Volume {numbers.in_words(book.volume).title()}"
        head.append(line)
    if book.imprint:
        head.append(book.imprint)

    isbn = book.isbn.get(book.primary().name)
    head.append(f"ISBN: {isbn} ({book.primary().name})" if isbn else "ISBN: forthcoming")

    editions = ", ".join(f"{t.name} ({t.width:g} x {t.height:g} in)" for t in book.trims)
    head.append(f"Editions: {editions}")
    head.append("")
    if book.tagline:
        head.append(f"Tagline: {book.tagline.rstrip('.')}")
        head.append("")
    return "\n".join(head) + "\n" + book.description.strip() + "\n"


def write_listing(book, dist_dir) -> str:
    path = os.path.join(dist_dir, f"{book.slug}-description.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(listing_text(book))
    return path


def build(directory, *, covers=True, html=True) -> Result:
    """Build the book in *directory*."""
    book = config.load(directory)
    template = templates.get(book.template)

    dist_dir = book.dist_dir
    render_dir = os.path.join(dist_dir, "_render")
    os.makedirs(render_dir, exist_ok=True)

    result = Result(slug=book.slug, title=book.title, template=book.template)
    try:
        pdfs, pages = template.build_pdf(book, dist_dir, render_dir)
        result.pdfs, result.pages = list(pdfs), dict(pages)

        if html:
            result.html = template.build_html(book, dist_dir)

        if covers and cover.has_art(book.art_dir):
            result.pdfs += cover.build(book, render_dir, pages)

        if book.description:
            result.description = write_listing(book, dist_dir)

        pdftools.embed_fonts_in(result.pdfs)
    finally:
        shutil.rmtree(render_dir, ignore_errors=True)

    return result


def build_all(root, selectors=None, **kwargs):
    """Build every book under *root*, or those whose slug or path matches a selector."""
    results = []
    for directory in config.discover(root):
        book = config.load(directory)
        if selectors and not any(
                s == book.slug or s in directory for s in selectors):
            continue
        results.append(build(directory, **kwargs))
    return results
