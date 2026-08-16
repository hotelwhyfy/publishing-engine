"""Font registration and text metrics.

reportlab's built-in Times and Helvetica are *not* embedded in the output PDF, which
most print services reject. So real TrueType files are registered under stable internal
names and those are used everywhere:

===============  =========================================
``BookSerif``    body text, in regular / -B / -I / -BI
``BookMono``     formulas, folios and code, in regular / -B
``BookSans``     incidental label text
===============  =========================================

Files are found automatically — Liberation (metric-compatible with Times/Courier/Arial)
first, then the macOS equivalents. A book may override any family by giving explicit
paths in its config::

    [fonts]
    serif = ["Regular.ttf", "Bold.ttf", "Italic.ttf", "BoldItalic.ttf"]
    mono  = ["Mono.ttf", "MonoBold.ttf"]
    sans  = "Sans.ttf"
"""
from __future__ import annotations

import os

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SERIF, SERIF_B, SERIF_I, SERIF_BI = "BookSerif", "BookSerif-B", "BookSerif-I", "BookSerif-BI"
MONO, MONO_B = "BookMono", "BookMono-B"
SANS = "BookSans"

_SERIF_SETS = [
    ("/usr/share/fonts/truetype/liberation/",
     ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf",
      "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf")),
    ("/System/Library/Fonts/Supplemental/",
     ("Times New Roman.ttf", "Times New Roman Bold.ttf",
      "Times New Roman Italic.ttf", "Times New Roman Bold Italic.ttf")),
]
_MONO_SETS = [
    ("/usr/share/fonts/truetype/liberation/",
     ("LiberationMono-Regular.ttf", "LiberationMono-Bold.ttf")),
    ("/System/Library/Fonts/Supplemental/",
     ("Courier New.ttf", "Courier New Bold.ttf")),
]
_SANS_FILES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

_registered = False


class FontError(Exception):
    """No usable font files were found."""


def _resolve(sets, what):
    for directory, files in sets:
        if all(os.path.exists(directory + f) for f in files):
            return [directory + f for f in files]
    raise FontError(
        f"no {what} font files found. Install the Liberation fonts, or set "
        f"[fonts].{what} in the book config to explicit paths.")


def register(overrides: dict | None = None) -> None:
    """Register every family once. Safe to call repeatedly.

    *overrides* may carry ``serif`` (4 paths), ``mono`` (2 paths) and ``sans`` (1 path).
    """
    global _registered
    if _registered:
        return
    overrides = overrides or {}

    serif = overrides.get("serif") or _resolve(_SERIF_SETS, "serif")
    for name, path in zip((SERIF, SERIF_B, SERIF_I, SERIF_BI), serif):
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(SERIF, normal=SERIF, bold=SERIF_B,
                                  italic=SERIF_I, boldItalic=SERIF_BI)

    mono = overrides.get("mono") or _resolve(_MONO_SETS, "mono")
    for name, path in zip((MONO, MONO_B), mono):
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(MONO, normal=MONO, bold=MONO_B)

    sans = overrides.get("sans")
    if not sans:
        sans = next((p for p in _SANS_FILES if os.path.exists(p)), None)
    if not sans:
        raise FontError("no sans font found; set [fonts].sans in the book config")
    pdfmetrics.registerFont(TTFont(SANS, sans))

    _registered = True


def reset() -> None:
    """Forget that registration happened. Only useful in tests."""
    global _registered
    _registered = False


def color(value):
    """``'1b4f9c'`` or ``'#1b4f9c'`` -> a reportlab colour."""
    return HexColor(int(str(value).lstrip("#"), 16))


def fit_tracking(text, font, size, tracking, max_width, min_size=9, min_tracking=0.4):
    """Shrink letter-spacing, then point size, until *text* fits *max_width*.

    Returns the ``(size, tracking)`` that fits. Tracking gives way first because losing
    a little letter-spacing is less visible than losing type size.
    """
    def width(sz, tr):
        return (pdfmetrics.stringWidth(text, font, sz)
                + tr * max(len(text) - 1, 0))

    while width(size, tracking) > max_width and tracking > min_tracking:
        tracking -= 0.3
    while width(size, tracking) > max_width and size > min_size:
        size -= 0.5
    return size, tracking


def wrap_lines(text, font, size, max_width):
    """Break *text* into lines that each fit within *max_width*."""
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and pdfmetrics.stringWidth(trial, font, size) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def wrap_centred(canvas, cx, y, text, font, size, max_width, leading=None, anchor="top"):
    """Draw *text* centred on *cx*, wrapped to *max_width*.

    Front-matter lines — subtitles, taglines, epigraphs — are drawn as free-standing
    centred strings rather than flowed paragraphs, so they do not wrap on their own and
    a long one will run straight through the page frame. This wraps them.

    ``anchor="top"`` puts the first line on *y* and stacks the rest downward.
    ``anchor="bottom"`` puts the *last* line on *y* and stacks upward, which is what you
    want when something fixed sits below, such as an imprint at the foot of the page.

    Returns the baseline of the last line drawn.
    """
    if not text:
        return y
    leading = leading or size * 1.28
    lines = wrap_lines(text, font, size, max_width)
    if anchor == "bottom":
        y += (len(lines) - 1) * leading
    canvas.setFont(font, size)
    for i, line in enumerate(lines):
        canvas.drawCentredString(cx, y - i * leading, line)
    return y - (len(lines) - 1) * leading
