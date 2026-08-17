"""Turning data coordinates into page coordinates, and choosing where the ticks go.

Two jobs. :class:`Scale` maps a data range onto a pixel range — and flips the y axis,
because data goes up and SVG goes down. :func:`nice_ticks` picks round numbers to label,
which is the difference between an axis reading 0, 0.5, 1, 1.5 and one reading
0, 0.4285, 0.8571.
"""
from __future__ import annotations

import math

#: Tick steps worth landing on, as multiples of a power of ten.
_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)


def nice_step(rough):
    """Round a rough step up to the next value that reads well."""
    if rough <= 0 or not math.isfinite(rough):
        return 1.0
    power = 10.0 ** math.floor(math.log10(rough))
    for step in _STEPS:
        if rough <= step * power * 1.0000001:
            return step * power
    return 10.0 * power


def nice_ticks(low, high, target=6):
    """Round tick positions spanning *low* to *high*, roughly *target* of them."""
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return [low] if math.isfinite(low) else []
    step = nice_step((high - low) / max(target, 1))
    start = math.ceil(low / step - 1e-9) * step
    ticks, value, guard = [], start, 0
    while value <= high + step * 1e-9 and guard < 1000:
        # snap values that are a hair off zero, so "-0" never reaches a label
        ticks.append(0.0 if abs(value) < step * 1e-9 else value)
        value += step
        guard += 1
    return ticks


def format_tick(value, step=None):
    """Label a tick with as few decimal places as tell it apart from its neighbours."""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    places = 6
    if step:
        places = max(0, min(6, int(math.ceil(-math.log10(abs(step)))) + 1))
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def padded(low, high, fraction=0.08):
    """Widen a range slightly so marks do not sit against the frame."""
    if high < low:
        low, high = high, low
    span = high - low
    if span <= 0:
        span = abs(high) or 1.0
        return low - span * 0.5, high + span * 0.5
    return low - span * fraction, high + span * fraction


class Scale:
    """Maps one data axis onto one pixel axis."""

    def __init__(self, lo, hi, pixel_lo, pixel_hi, invert=False):
        if hi == lo:                       # a flat range still has to map somewhere
            hi = lo + 1.0
        self.lo, self.hi = float(lo), float(hi)
        self.pixel_lo, self.pixel_hi = float(pixel_lo), float(pixel_hi)
        self.invert = invert

    def __call__(self, value):
        t = (float(value) - self.lo) / (self.hi - self.lo)
        if self.invert:
            return self.pixel_hi - t * (self.pixel_hi - self.pixel_lo)
        return self.pixel_lo + t * (self.pixel_hi - self.pixel_lo)

    def contains(self, value):
        return self.lo <= value <= self.hi

    def clamp(self, value):
        return min(max(float(value), self.lo), self.hi)

    @property
    def span(self):
        return self.hi - self.lo
