"""A very small SVG writer.

Enough to draw a figure and no more. Everything is written as inline attributes rather
than CSS classes, because the rasteriser that turns these into print images does not
apply stylesheets.

**Text is never set in a real italic.** The rasteriser's fallback font inserts a spurious
space after every ``f`` in italic text — ``f(x) flows`` comes out as ``f (x) f lows`` —
and mathematical labels are full of ``f``. :func:`text` takes ``slant=True`` instead,
which leans the glyphs with a transform and leaves the spacing alone.
"""
from __future__ import annotations

_ESCAPES = ((("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")))


def escape(value):
    text = str(value)
    for old, new in _ESCAPES:
        text = text.replace(old, new)
    return text


def _fmt(value):
    """Trim float noise: 3.0000000004 is 3, and 0.30000000000000004 is 0.3."""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return "0"
        return f"{value:.3f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _attrs(pairs):
    out = []
    for key, value in pairs.items():
        if value is None or value is False:
            continue
        if value is True:
            value = "true"
        out.append(f'{key.replace("_", "-")}="{escape(_fmt(value))}"')
    return (" " + " ".join(out)) if out else ""


def element(tag, **attrs):
    return f"<{tag}{_attrs(attrs)}/>"


def group(body, **attrs):
    inner = "\n  ".join(b for b in body if b)
    return f"<g{_attrs(attrs)}>\n  {inner}\n</g>" if inner else ""


def rect(x, y, width, height, **attrs):
    return element("rect", x=x, y=y, width=max(width, 0), height=max(height, 0), **attrs)


def line(x1, y1, x2, y2, **attrs):
    return element("line", x1=x1, y1=y1, x2=x2, y2=y2, **attrs)


def circle(cx, cy, r, **attrs):
    return element("circle", cx=cx, cy=cy, r=r, **attrs)


def path(commands, **attrs):
    return element("path", d=commands, **attrs)


def polyline(points, **attrs):
    """A run of points as one path. Returns nothing for a run too short to draw."""
    points = [p for p in points if p is not None]
    if len(points) < 2:
        return ""
    head = f"M{_fmt(points[0][0])},{_fmt(points[0][1])}"
    tail = " ".join(f"L{_fmt(x)},{_fmt(y)}" for x, y in points[1:])
    return path(f"{head} {tail}", **attrs)


def text(x, y, content, *, size=10, color="#000", anchor="start", weight=None,
         slant=False, family="Georgia,serif", **attrs):
    """A text run. Use ``slant=True`` rather than a real italic — see the module note."""
    transform = f"skewX(-12) translate({_fmt(y * 0.2126)},0)" if slant else None
    return (f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-family="{escape(family)}" '
            f'font-size="{_fmt(size)}" fill="{escape(color)}" text-anchor="{anchor}"'
            f'{_attrs({"font_weight": weight, "transform": transform, **attrs})}>'
            f"{escape(content)}</text>")


def document(width, height, body, background=None):
    parts = [f'<svg viewBox="0 0 {_fmt(width)} {_fmt(height)}" '
             f'xmlns="http://www.w3.org/2000/svg">']
    if background:
        parts.append(rect(0, 0, width, height, fill=background))
    parts.extend(b for b in body if b)
    parts.append("</svg>")
    return "\n".join(parts)
