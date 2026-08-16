"""One inline markup, rendered to PDF, to HTML, or to bare text.

Content is authored once and set twice — into the print PDF and into the reading HTML —
so the markup has to be neutral about which::

    **bold**      ->  <b>        / <strong>
    *italic*      ->  <i>        / <em>
    `mono`        ->  mono font  / <code>
    x^{n}         ->  superscript
    x_{i}         ->  subscript

Literal Unicode is fine (—, ·, ², ′, →, ∫, …). Two glyphs are swapped on the PDF side
because Times and Liberation have no drawing for them: the double and triple integrals
are expanded into repeated single integrals, and the implies-arrow — which those fonts
carry as a blank — becomes a plain arrow. HTML keeps the originals.
"""
from __future__ import annotations

import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITAL = re.compile(r"\*(.+?)\*")
_MONO = re.compile(r"`(.+?)`")
_SUP = re.compile(r"\^\{(.+?)\}")
_SUB = re.compile(r"_\{(.+?)\}")

#: Glyphs missing or blank in the standard serif faces, and what to draw instead.
PDF_SUBSTITUTIONS = {"∬": "∫∫", "∭": "∫∫∫", "⇒": "→"}


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_reportlab(s, mono="BookMono", mono_size=10, mono_color="#0e2a52"):
    """Render to reportlab's inline markup, for use inside a Paragraph."""
    s = _escape(s)
    for bad, good in PDF_SUBSTITUTIONS.items():
        s = s.replace(bad, good)
    s = _MONO.sub(
        lambda m: f'<font name="{mono}" size="{mono_size}" color="{mono_color}">{m.group(1)}</font>', s)
    s = _SUP.sub(r"<super>\1</super>", s)
    s = _SUB.sub(r"<sub>\1</sub>", s)
    s = _BOLD.sub(r"<b>\1</b>", s)
    s = _ITAL.sub(r"<i>\1</i>", s)
    return s


def to_html(s):
    """Render to HTML."""
    s = _escape(s)
    s = _MONO.sub(r"<code>\1</code>", s)
    s = _SUP.sub(r"<sup>\1</sup>", s)
    s = _SUB.sub(r"<sub>\1</sub>", s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITAL.sub(r"<em>\1</em>", s)
    return s


def plain(s):
    """Strip the markup, leaving bare text — for captions drawn into SVG or plain text."""
    for pattern in (_MONO, _SUP, _SUB, _BOLD, _ITAL):
        s = pattern.sub(r"\1", s)
    return s


def paragraphs(block):
    """Split a triple-quoted block into paragraphs on blank lines."""
    return [p.strip() for p in re.split(r"\n\s*\n", block.strip()) if p.strip()]
