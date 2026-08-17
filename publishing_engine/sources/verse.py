"""Parse a content file into sections of numbered lines.

For books built out of short numbered units — proverbs, aphorisms, rules, clauses::

    # Section title           begins a section; the rest of the line is its title
    One line per unit         each becomes the next numbered entry in that section
    ![Caption](art/fig.svg)   a figure, sitting between entries
    ![Caption](plot:name)     a figure the book declares
    // comment                ignored

Numbering restarts at 1 in each section and is generated at layout time, so entries can
be added or reordered without renumbering anything by hand. A file may open with
entries before any heading; those become an untitled leading section.

An entry is a plain string. A figure is a dict, and is not numbered — so a figure can be
dropped in anywhere without shifting the numbers around it.
"""
from __future__ import annotations

import re

_IMAGE = re.compile(r"^!\[(?P<caption>.*?)\]\((?P<src>[^)]+)\)(?P<attr>\{[^}]*\})?\s*$")


def parse(path):
    sections = []
    current = None

    def section():
        nonlocal current
        if current is None:
            current = {"name": None, "entries": []}
            sections.append(current)
        return current

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("#"):
                current = {"name": line.lstrip("#").strip(), "entries": []}
                sections.append(current)
                continue
            match = _IMAGE.match(line)
            if match:
                caption = match.group("caption").strip()
                attr = (match.group("attr") or "").lower()
                section()["entries"].append({
                    "type": "image", "src": match.group("src").strip(),
                    "caption": caption,
                    "full": ("full" in attr) or (caption == "" and "inline" not in attr),
                })
            else:
                section()["entries"].append(line)

    return [s for s in sections if s["entries"]]
