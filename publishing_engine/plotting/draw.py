"""Render a declared figure to SVG, in the book's own colours.

Two kinds of figure share this renderer, because they share almost everything — a frame,
scales, ticks, a grid, labels:

``plot``
    numeric axes carrying curves from expressions, shaded regions, marked points,
    reference lines, tangents and notes.

``chart``
    the same axes carrying data series — bars, lines, steps or scatter — over either
    numbers or named categories.

Figures are drawn on a 600-unit-wide canvas and scaled to the column when placed, so
sizes here are relative to that, not to points on the finished page.
"""
from __future__ import annotations

import math

from . import svg
from .expr import ExpressionError, as_number, compile_expr
from .scale import Scale, format_tick, nice_ticks, padded

#: Internal canvas width. Height follows from the figure's aspect.
WIDTH = 600.0
#: Room for tick labels and axis titles.
MARGIN = {"left": 52.0, "right": 20.0, "top": 20.0, "bottom": 40.0}
#: How many points a curve is sampled at across the x range.
SAMPLES = 420


class FigureError(Exception):
    """A figure spec is malformed."""


# ---------------------------------------------------------------------------
# theme
# ---------------------------------------------------------------------------

def _theme_colors(theme):
    return {
        "paper": f"#{theme.paper}", "ink": f"#{theme.ink}",
        "accent": f"#{theme.accent}", "accent2": f"#{theme.accent2}",
        "mute": f"#{theme.mute}", "rule": f"#{theme.rule}",
        "faint": f"#{theme.faint}", "mono": f"#{theme.mono_ink}",
    }


def _color(value, colors, default="accent"):
    """A theme name, or a hex value with or without its hash."""
    if not value:
        return colors[default]
    value = str(value)
    if value in colors:
        return colors[value]
    return value if value.startswith("#") else f"#{value}"


def _cycle(colors):
    return [colors["accent"], colors["accent2"], colors["mono"], colors["mute"]]


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------

def _sample(fn, lo, hi, count=SAMPLES, skip=()):
    """Evaluate *fn* across a range, yielding ``(x, y)`` or None where it has no value.

    A None marks a break in the line — a division by zero, a negative square root, or a
    point the author has declared a hole. Without them a curve either side of an
    asymptote would be joined by a vertical stroke that is not part of the function.
    """
    out = []
    step = (hi - lo) / float(count - 1)
    tolerance = abs(step) * 0.75
    for i in range(count):
        x = lo + i * step
        if any(abs(x - h) < tolerance for h in skip):
            out.append(None)
            continue
        try:
            y = fn(x)
        except (ZeroDivisionError, ValueError, OverflowError, ExpressionError):
            out.append(None)
            continue
        if isinstance(y, bool) or not isinstance(y, (int, float)):
            out.append(None)
        elif math.isfinite(y):
            out.append((x, float(y)))
        else:
            out.append(None)
    return out


def _auto_range(values, fallback=(0.0, 1.0)):
    """A y range that ignores the blow-up near an asymptote."""
    finite = sorted(v for v in values if v is not None and math.isfinite(v))
    if not finite:
        return fallback
    if len(finite) < 8:
        return padded(min(finite), max(finite))
    lo = finite[int(len(finite) * 0.02)]
    hi = finite[int(len(finite) * 0.98) - 1]
    if hi <= lo:
        lo, hi = min(finite), max(finite)
    return padded(lo, hi)


def _segments(points, yscale=None, jump=None):
    """Split a sampled run into unbroken segments, breaking at None and at big jumps."""
    runs, current, previous = [], [], None
    for point in points:
        if point is None:
            if len(current) > 1:
                runs.append(current)
            current, previous = [], None
            continue
        if previous is not None and jump is not None and abs(point[1] - previous[1]) > jump:
            if len(current) > 1:
                runs.append(current)
            current = []
        current.append(point)
        previous = point
    if len(current) > 1:
        runs.append(current)
    return runs


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def aspect(spec):
    """Width divided by height, for placing the figure before it is drawn."""
    try:
        value = float(spec.get("aspect", 1.6))
    except (TypeError, ValueError):
        value = 1.6
    return value if value > 0 else 1.6


def _categories(spec):
    labels = spec.get("x")
    if isinstance(labels, list) and labels and all(isinstance(v, str) for v in labels):
        return labels
    return None


def _plot_ranges(spec, layers):
    """Work out the x and y ranges, from the spec where given and the data where not."""
    xr = spec.get("x")
    if isinstance(xr, list) and len(xr) == 2 and not _categories(spec):
        xlo, xhi = as_number(xr[0]), as_number(xr[1])
    else:
        xlo, xhi = -5.0, 5.0
    yr = spec.get("y")
    if isinstance(yr, list) and len(yr) == 2:
        return (xlo, xhi), (as_number(yr[0]), as_number(yr[1]))

    values = []
    for points in layers:
        values.extend(p[1] for p in points if p is not None)
    for point in spec.get("point", []):
        at = point.get("at")
        if isinstance(at, list) and len(at) == 2:
            values.append(as_number(at[1]))
    return (xlo, xhi), _auto_range(values)


# ---------------------------------------------------------------------------
# furniture
# ---------------------------------------------------------------------------

def _frame_and_ticks(spec, sx, sy, box, colors, categories=None):
    left, right, top, bottom = box
    body = []
    grid = spec.get("grid", True)
    show_axes = spec.get("axes", True)

    xticks = (list(range(len(categories))) if categories
              else nice_ticks(sx.lo, sx.hi, spec.get("xticks", 6)))
    yticks = nice_ticks(sy.lo, sy.hi, spec.get("yticks", 5))
    xstep = (xticks[1] - xticks[0]) if len(xticks) > 1 else None
    ystep = (yticks[1] - yticks[0]) if len(yticks) > 1 else None

    if grid:
        # a vertical rule through the middle of a bar is noise, so categorical
        # charts get horizontal grid only — the axis you actually read against
        if not categories:
            for value in xticks:
                x = sx(value)
                body.append(svg.line(x, top, x, bottom, stroke=colors["faint"],
                                     stroke_width=0.6, opacity=0.35))
        for value in yticks:
            y = sy(value)
            body.append(svg.line(left, y, right, y, stroke=colors["faint"],
                                 stroke_width=0.6, opacity=0.35))

    # the axes proper: through zero when zero is in view, otherwise along the frame
    if show_axes:
        zero_y = sy(0.0) if sy.contains(0) else bottom
        zero_x = sx(0.0) if (not categories and sx.contains(0)) else left
        body.append(svg.line(left, zero_y, right, zero_y, stroke=colors["ink"],
                             stroke_width=1.1))
        body.append(svg.line(zero_x, top, zero_x, bottom, stroke=colors["ink"],
                             stroke_width=1.1))
    else:
        body.append(svg.rect(left, top, right - left, bottom - top, fill="none",
                             stroke=colors["mute"], stroke_width=0.9))

    baseline = sy(0.0) if (show_axes and sy.contains(0)) else bottom
    for i, value in enumerate(xticks):
        x = sx(value)
        label = categories[i] if categories else format_tick(value, xstep)
        if not categories and abs(value) < (xstep or 1) * 1e-9:
            continue                          # the origin is labelled once, on the y axis
        body.append(svg.line(x, baseline, x, baseline + 3.5, stroke=colors["mute"],
                             stroke_width=0.8))
        body.append(svg.text(x, baseline + 14, label, size=10, color=colors["mute"],
                             anchor="middle"))

    origin_shown = show_axes and not categories and sx.contains(0) and sy.contains(0)
    axis_x = sx(0.0) if (show_axes and not categories and sx.contains(0)) else left
    for value in yticks:
        y = sy(value)
        at_origin = origin_shown and abs(value) < (ystep or 1) * 1e-9
        body.append(svg.line(axis_x - 3.5, y, axis_x, y, stroke=colors["mute"],
                             stroke_width=0.8))
        # the origin's label is dropped below the axis, or it sits on top of it
        body.append(svg.text(axis_x - 6, y + (14 if at_origin else 3.4),
                             format_tick(value, ystep), size=10,
                             color=colors["mute"], anchor="end"))

    if spec.get("xlabel"):
        body.append(svg.text(right, bottom + 28, spec["xlabel"], size=11,
                             color=colors["ink"], anchor="end", slant=True))
    if spec.get("ylabel"):
        # sits above the axis and reads rightward: anchoring it to the axis instead
        # would run a long label off the left of the canvas, where it is cut off
        body.append(svg.text(6, top - 8, spec["ylabel"], size=11,
                             color=colors["ink"], anchor="start", slant=True))
    if spec.get("title"):
        body.append(svg.text((left + right) / 2, top - 8, spec["title"], size=11.5,
                             color=colors["accent"], anchor="middle"))
    return body


# ---------------------------------------------------------------------------
# plot layers
# ---------------------------------------------------------------------------

def _draw_plot(spec, sx, sy, box, colors):
    left, right, top, bottom = box
    palette = _cycle(colors)
    body, legend = [], []
    jump = sy.span * 0.45

    def to_px(points):
        return [(sx(x), sy(y)) for x, y in points]

    # shaded regions first, so curves and marks sit on top
    for index, area in enumerate(spec.get("area", [])):
        if "of" not in area:
            raise FigureError("[[figure.area]] needs 'of'")
        fn = compile_expr(area["of"])
        lo = as_number(area.get("from", sx.lo))
        hi = as_number(area.get("to", sx.hi))
        under = compile_expr(area["under"]) if area.get("under") else (lambda _x: 0.0)
        samples = [p for p in _sample(fn, lo, hi, 160) if p is not None]
        if len(samples) < 2:
            continue
        upper = to_px(samples)
        lower = []
        for x, _ in reversed(samples):
            try:
                lower.append((sx(x), sy(under(x))))
            except (ZeroDivisionError, ValueError, OverflowError):
                lower.append((sx(x), sy(0.0)))
        commands = ("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower) + " Z")
        body.append(svg.path(commands, fill=_color(area.get("color"), colors),
                             opacity=float(area.get("opacity", 0.16)), stroke="none"))
        if area.get("label"):
            mid = samples[len(samples) // 2]
            body.append(svg.text(sx(mid[0]), sy(mid[1] / 2.0), area["label"], size=11,
                                 color=colors["ink"], anchor="middle"))

    for index, curve in enumerate(spec.get("curve", [])):
        if "of" not in curve:
            raise FigureError("[[figure.curve]] needs 'of'")
        fn = compile_expr(curve["of"])
        holes = [as_number(h) for h in curve.get("holes", [])]
        color = _color(curve.get("color"), colors) if curve.get("color") \
            else palette[index % len(palette)]
        points = _sample(fn, sx.lo, sx.hi, skip=holes)
        for run in _segments(points, jump=jump):
            clipped = [(x, y) for x, y in run if sy.lo - sy.span <= y <= sy.hi + sy.span]
            if len(clipped) > 1:
                body.append(svg.polyline(to_px(clipped), fill="none", stroke=color,
                                         stroke_width=float(curve.get("width", 2.0)),
                                         stroke_dasharray="5 4" if curve.get("dash") else None,
                                         stroke_linecap="round", stroke_linejoin="round"))
        # a removable discontinuity: an open circle at the value the curve approaches
        for hole in holes:
            nearby = [fn(hole + d) for d in (-1e-4, 1e-4)
                      if _safe(fn, hole + d) is not None]
            if nearby:
                body.append(svg.circle(sx(hole), sy(sum(nearby) / len(nearby)), 3.4,
                                       fill=colors["paper"], stroke=color, stroke_width=1.6))
        if curve.get("label"):
            legend.append((curve["label"], color))

    for mark in spec.get("point", []):
        at = mark.get("at")
        if not (isinstance(at, list) and len(at) == 2):
            raise FigureError("[[figure.point]] needs at = [x, y]")
        x, y = sx(as_number(at[0])), sy(as_number(at[1]))
        color = _color(mark.get("color"), colors)
        open_style = str(mark.get("style", "filled")) == "open"
        body.append(svg.circle(x, y, float(mark.get("size", 3.6)),
                               fill=colors["paper"] if open_style else color,
                               stroke=color, stroke_width=1.6))
        if mark.get("label"):
            body.append(svg.text(x + 8, y - 6, mark["label"], size=10.5,
                                 color=colors["ink"]))

    for rule in spec.get("line", []):
        color = _color(rule.get("color"), colors, "mute")
        dash = "4 4" if rule.get("dash", True) else None
        if "y" in rule:
            y = sy(as_number(rule["y"]))
            body.append(svg.line(left, y, right, y, stroke=color, stroke_width=1.1,
                                 stroke_dasharray=dash))
            if rule.get("label"):
                body.append(svg.text(right - 4, y - 5, rule["label"], size=10,
                                     color=color, anchor="end"))
        elif "x" in rule:
            x = sx(as_number(rule["x"]))
            body.append(svg.line(x, top, x, bottom, stroke=color, stroke_width=1.1,
                                 stroke_dasharray=dash))
            if rule.get("label"):
                body.append(svg.text(x + 4, top + 12, rule["label"], size=10, color=color))
        else:
            raise FigureError("[[figure.line]] needs x or y")

    for tangent in spec.get("tangent", []):
        if "of" not in tangent or "at" not in tangent:
            raise FigureError("[[figure.tangent]] needs 'of' and 'at'")
        fn = compile_expr(tangent["of"])
        a = as_number(tangent["at"])
        h = sx.span * 1e-4
        try:
            slope = (fn(a + h) - fn(a - h)) / (2 * h)
            value = fn(a)
        except (ZeroDivisionError, ValueError, OverflowError):
            continue
        reach = sx.span * float(tangent.get("reach", 0.22))
        x0, x1 = a - reach, a + reach
        color = _color(tangent.get("color"), colors, "accent2")
        body.append(svg.polyline([(sx(x0), sy(value + slope * (x0 - a))),
                                  (sx(x1), sy(value + slope * (x1 - a)))],
                                 fill="none", stroke=color, stroke_width=1.6,
                                 stroke_dasharray="6 4"))
        if tangent.get("point", True):
            body.append(svg.circle(sx(a), sy(value), 3.2, fill=color, stroke="none"))
        if tangent.get("label"):
            body.append(svg.text(sx(x1) + 4, sy(value + slope * (x1 - a)),
                                 tangent["label"], size=10, color=color))

    for note in spec.get("note", []):
        at = note.get("at")
        if not (isinstance(at, list) and len(at) == 2):
            raise FigureError("[[figure.note]] needs at = [x, y]")
        body.append(svg.text(sx(as_number(at[0])), sy(as_number(at[1])),
                             note.get("text", ""), size=float(note.get("size", 10.5)),
                             color=_color(note.get("color"), colors, "ink"),
                             anchor=note.get("anchor", "start"),
                             slant=bool(note.get("slant", False))))

    return body, legend


def _safe(fn, x):
    try:
        y = fn(x)
        return y if math.isfinite(y) else None
    except (ZeroDivisionError, ValueError, OverflowError, ExpressionError):
        return None


# ---------------------------------------------------------------------------
# chart layers
# ---------------------------------------------------------------------------

def _series_points(series, categories):
    values = series.get("values")
    if not isinstance(values, list) or not values:
        raise FigureError("[[figure.series]] needs a non-empty 'values'")
    at = series.get("at")
    if isinstance(at, list) and len(at) == len(values):
        xs = [as_number(v) for v in at]
    else:
        xs = list(range(len(values)))
    return [(x, as_number(v)) for x, v in zip(xs, values)]


def _chart_ranges(spec, all_points, categories):
    if categories:
        xlo, xhi = -0.6, len(categories) - 0.4
    else:
        xs = [p[0] for p in all_points] or [0.0, 1.0]
        xlo, xhi = min(xs), max(xs)
        if xlo == xhi:
            xlo, xhi = xlo - 1, xhi + 1
    xr = spec.get("x")
    if isinstance(xr, list) and len(xr) == 2 and not categories:
        xlo, xhi = as_number(xr[0]), as_number(xr[1])

    yr = spec.get("y")
    if isinstance(yr, list) and len(yr) == 2:
        return (xlo, xhi), (as_number(yr[0]), as_number(yr[1]))
    ys = [p[1] for p in all_points] or [0.0, 1.0]
    low, high = min(ys), max(ys)
    low = min(low, 0.0)                      # bars are read against zero
    return (xlo, xhi), (low, high + (high - low) * 0.12 if high > low else high + 1)


def _draw_chart(spec, sx, sy, box, colors, categories, series_specs):
    left, right, top, bottom = box
    palette = _cycle(colors)
    body, legend = [], []
    bars = [s for s in series_specs if str(s.get("type", "bar")) == "bar"]
    baseline = sy(max(sy.lo, 0.0))

    for index, series in enumerate(series_specs):
        points = _series_points(series, categories)
        kind = str(series.get("type", "bar"))
        color = _color(series.get("color"), colors) if series.get("color") \
            else palette[index % len(palette)]

        if kind == "bar":
            slot = (sx(1) - sx(0)) if categories or len(points) > 1 else 40.0
            width = abs(slot) * float(spec.get("bar_width", 0.72)) / max(len(bars), 1)
            offset = (bars.index(series) - (len(bars) - 1) / 2.0) * width
            for x, y in points:
                cx = sx(x) + offset
                top_y, bottom_y = min(sy(y), baseline), max(sy(y), baseline)
                body.append(svg.rect(cx - width / 2, top_y, width, bottom_y - top_y,
                                     fill=color, opacity=float(series.get("opacity", 1.0))))
                if series.get("values_shown", spec.get("values_shown", False)):
                    body.append(svg.text(cx, top_y - 4, format_tick(y), size=9,
                                         color=colors["mute"], anchor="middle"))
        elif kind == "scatter":
            for x, y in points:
                body.append(svg.circle(sx(x), sy(y), float(series.get("size", 3.4)),
                                       fill=color, stroke="none"))
        elif kind == "step":
            path = []
            for i, (x, y) in enumerate(points):
                if i:
                    path.append((sx(x), sy(points[i - 1][1])))
                path.append((sx(x), sy(y)))
            body.append(svg.polyline(path, fill="none", stroke=color, stroke_width=2.0,
                                     stroke_linejoin="round"))
        else:                                  # line
            body.append(svg.polyline([(sx(x), sy(y)) for x, y in points], fill="none",
                                     stroke=color, stroke_width=2.0,
                                     stroke_dasharray="5 4" if series.get("dash") else None,
                                     stroke_linecap="round", stroke_linejoin="round"))
            if series.get("points", False):
                for x, y in points:
                    body.append(svg.circle(sx(x), sy(y), 3.0, fill=color, stroke="none"))

        if series.get("label"):
            legend.append((series["label"], color))
    return body, legend


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def _legend(entries, box, colors):
    if not entries:
        return []
    left, right, top, _bottom = box
    body = []
    y = top + 12
    for label, color in entries:
        body.append(svg.line(right - 116, y - 4, right - 98, y - 4, stroke=color,
                             stroke_width=2.4, stroke_linecap="round"))
        body.append(svg.text(right - 92, y, label, size=10, color=colors["ink"]))
        y += 15
    return body


def render(spec, theme):
    """Draw *spec* and return a complete SVG document."""
    if not isinstance(spec, dict):
        raise FigureError("a figure spec must be a table")
    colors = _theme_colors(theme)
    height = WIDTH / aspect(spec)
    box = (MARGIN["left"], WIDTH - MARGIN["right"], MARGIN["top"], height - MARGIN["bottom"])
    left, right, top, bottom = box
    categories = _categories(spec)
    kind = str(spec.get("kind", "chart" if spec.get("series") else "plot"))

    if kind == "chart":
        series_specs = spec.get("series", [])
        if not series_specs:
            raise FigureError(f"chart '{spec.get('name')}' has no [[figure.series]]")
        all_points = []
        for series in series_specs:
            all_points.extend(_series_points(series, categories))
        (xlo, xhi), (ylo, yhi) = _chart_ranges(spec, all_points, categories)
        sx = Scale(xlo, xhi, left, right)
        sy = Scale(ylo, yhi, top, bottom, invert=True)
        layers, legend = _draw_chart(spec, sx, sy, box, colors, categories, series_specs)
    elif kind == "plot":
        sampled = []
        for curve in spec.get("curve", []):
            if "of" in curve:
                xr = spec.get("x")
                lo, hi = ((as_number(xr[0]), as_number(xr[1]))
                          if isinstance(xr, list) and len(xr) == 2 else (-5.0, 5.0))
                sampled.append(_sample(compile_expr(curve["of"]), lo, hi, 200,
                                       skip=[as_number(h) for h in curve.get("holes", [])]))
        (xlo, xhi), (ylo, yhi) = _plot_ranges(spec, sampled)
        sx = Scale(xlo, xhi, left, right)
        sy = Scale(ylo, yhi, top, bottom, invert=True)
        layers, legend = _draw_plot(spec, sx, sy, box, colors)
    else:
        raise FigureError(f"unknown figure kind '{kind}' (use 'plot' or 'chart')")

    body = _frame_and_ticks(spec, sx, sy, box, colors, categories)
    body += layers
    body += _legend(legend, box, colors)
    return svg.document(WIDTH, height, body, background=colors["paper"])
