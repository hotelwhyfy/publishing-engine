"""Parse a free-form content file into an ordered list of blocks.

The authoring format is markdown-shaped and deliberately small::

    # Heading                  a section heading
    ## Subheading              a lesser heading
    Ordinary text              body; consecutive lines join into one paragraph,
                               a blank line starts the next
    - An item                  a bulleted list; one item per line
    1. An item                 a numbered list; the numbers are re-generated
    > A pull quote             set centred and apart
    ---                        a section break (an ornament, centred)
    ![](art/plate.svg)         a full-page plate — empty caption means full page
    ![Caption](art/fig.svg)    an inline figure at column width, with that caption
    ![Caption](art/fig.svg){full}   a full-page plate that also carries a caption
    // comment                 ignored

Inline markup (``**bold**``, ``*italic*``, ``` `mono` ```, ``x^{n}``, ``x_{i}``) is left
alone here and handled downstream, so the same text can be set into PDF and HTML.

Each block is a dict with a ``type``: ``heading``, ``subheading``, ``p``, ``quote``,
``list``, ``break`` or ``image``.
"""
from __future__ import annotations

import re

_IMAGE = re.compile(r"^!\[(?P<caption>.*?)\]\((?P<src>[^)]+)\)(?P<attr>\{[^}]*\})?\s*$")
_BULLET = re.compile(r"^[-*+]\s+(?P<text>\S.*)$")
_NUMBER = re.compile(r"^\d+[.)]\s+(?P<text>\S.*)$")


def parse(path):
    blocks = []
    para: list[str] = []
    items: list[str] = []
    ordered = False

    def flush():
        """Close whichever run is open — a paragraph or a list, never both."""
        if para:
            blocks.append({"type": "p", "text": " ".join(para).strip()})
            para.clear()
        if items:
            blocks.append({"type": "list", "ordered": ordered, "items": list(items)})
            items.clear()

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n").strip()

            if not line:
                flush()
                continue
            if line.startswith("//"):
                continue

            match = _IMAGE.match(line)
            if match:
                flush()
                caption = match.group("caption").strip()
                attr = (match.group("attr") or "").lower()
                full = ("full" in attr) or (caption == "" and "inline" not in attr)
                blocks.append({"type": "image", "src": match.group("src").strip(),
                               "caption": caption, "full": full})
                continue
            if line in ("---", "***"):
                flush()
                blocks.append({"type": "break"})
                continue
            if line.startswith("## "):
                flush()
                blocks.append({"type": "subheading", "text": line[3:].strip()})
                continue
            if line.startswith("# "):
                flush()
                blocks.append({"type": "heading", "text": line[2:].strip()})
                continue
            if line.startswith("> "):
                flush()
                blocks.append({"type": "quote", "text": line[2:].strip()})
                continue

            bullet = _BULLET.match(line)
            number = _NUMBER.match(line)
            if bullet or number:
                wants_ordered = number is not None
                if items and wants_ordered != ordered:
                    flush()                    # a change of list kind starts a new list
                if para:
                    flush()
                ordered = wants_ordered
                items.append((number or bullet).group("text").strip())
                continue

            if items:
                items[-1] += " " + line        # a wrapped item continues its own line
                continue

            para.append(line)

    flush()
    return blocks
