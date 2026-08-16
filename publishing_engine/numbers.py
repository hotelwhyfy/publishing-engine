"""Numbers as words and as roman numerals, for volume lines and part dividers."""
from __future__ import annotations

_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
          "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
          "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def in_words(n):
    """``7 -> 'seven'``. Falls back to the numeral for anything out of range."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if 0 <= n < 20:
        return _UNITS[n]
    if 20 <= n < 100:
        tens, unit = divmod(n, 10)
        return _TENS[tens] + (f"-{_UNITS[unit]}" if unit else "")
    return str(n)


def roman(n):
    """``4 -> 'IV'``. Falls back to the numeral for anything out of range."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if not 0 < n < 4000:
        return str(n)
    out = []
    for value, numeral in _ROMAN:
        count, n = divmod(n, value)
        out.append(numeral * count)
    return "".join(out)
