"""The available templates, and how a book selects one.

A template is a pair of renderers over the same content — one to print PDF, one to
reading HTML — so a book is written once and issued twice. Each exposes:

``build_pdf(book, dist_dir, render_dir) -> (paths, {trim_name: page_count})``
``build_html(book, dist_dir) -> path``
"""
from __future__ import annotations

from . import atlas, prose, verse

TEMPLATES = {
    "prose": prose,
    "verse": verse,
    "atlas": atlas,
}


class UnknownTemplate(Exception):
    pass


def get(name):
    try:
        return TEMPLATES[name]
    except KeyError:
        known = ", ".join(sorted(TEMPLATES))
        raise UnknownTemplate(f"unknown template '{name}' (known: {known})") from None


def names():
    return sorted(TEMPLATES)
