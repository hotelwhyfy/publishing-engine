"""Parse a content file into sections of numbered lines.

For books built out of short numbered units — proverbs, aphorisms, rules, clauses::

    # Section title      begins a section; the rest of the line is its title
    One line per unit    each becomes the next numbered entry in that section
    // comment           ignored

Numbering restarts at 1 in each section and is generated at layout time, so entries can
be added or reordered without renumbering anything by hand. A file may open with
entries before any heading; those become an untitled leading section.
"""
from __future__ import annotations


def parse(path):
    sections = []
    current = None

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("#"):
                current = {"name": line.lstrip("#").strip(), "entries": []}
                sections.append(current)
            else:
                if current is None:
                    current = {"name": None, "entries": []}
                    sections.append(current)
                current["entries"].append(line)

    return [s for s in sections if s["entries"]]
