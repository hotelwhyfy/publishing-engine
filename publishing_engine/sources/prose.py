"""Parse a free-form content file into an ordered list of blocks.

The authoring format is markdown-shaped and deliberately small::

    # Heading                  a section heading
    ## Subheading              a lesser heading
    Ordinary text              body; consecutive lines join into one paragraph,
                               a blank line starts the next
    > A pull quote             set centred and apart
    ---                        a section break (an ornament, centred)
    ![](art/plate.svg)         a full-page plate — empty caption means full page
    ![Caption](art/fig.svg)    an inline figure at column width, with that caption
    ![Caption](art/fig.svg){full}   a full-page plate that also carries a caption
    // comment                 ignored

Inline markup (``**bold**``, ``*italic*``, ``` `mono` ```, ``x^{n}``, ``x_{i}``) is left
alone here and handled downstream, so the same text can be set into PDF and HTML.

Each block is a dict with a ``type``: ``heading``, ``subheading``, ``p``, ``quote``,
``break`` or ``image``.
"""
from __future__ import annotations

import re

_IMAGE = re.compile(r"^!\[(?P<caption>.*?)\]\((?P<src>[^)]+)\)(?P<attr>\{[^}]*\})?\s*$")


def parse(path):
    blocks = []
    para: list[str] = []

    def flush():
        if para:
            blocks.append({"type": "p", "text": " ".join(para).strip()})
            para.clear()

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

            para.append(line)

    flush()
    return blocks
