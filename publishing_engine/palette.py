"""Small colour helpers, used to derive CSS from a book's theme.

The theme carries a handful of flat hex values. The reading HTML needs a few things
those do not state directly — a backdrop that falls off toward the edges, a hairline
rule at partial opacity — so they are computed rather than asked for.
"""
from __future__ import annotations


def rgb(value):
    """``'a8802e'`` or ``'#a8802e'`` -> ``(168, 128, 46)``."""
    value = str(value).lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def hex_of(triple):
    return "".join(f"{max(0, min(255, int(round(c)))):02x}" for c in triple)


def shade(value, factor):
    """Lighten (*factor* > 1) or darken (*factor* < 1) a colour."""
    return hex_of(c * factor for c in rgb(value))


def rgba(value, alpha):
    """A CSS ``rgba()`` string for *value* at *alpha*."""
    r, g, b = rgb(value)
    return f"rgba({r},{g},{b},{alpha})"


def backdrop(value):
    """A CSS radial gradient around *value*, lighter at the top, darker at the edges."""
    return (f"radial-gradient(120% 80% at 50% 0%, #{shade(value, 1.9)} 0%, "
            f"#{shade(value, 1.25)} 50%, #{shade(value, 0.6)} 100%)")
