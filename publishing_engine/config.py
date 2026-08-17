"""Read a book's TOML into a normalised :class:`Book`.

One config file describes one edition of one book: its metadata, its theme, the trims
it is printed at, and where its content lives. Everything a template needs is resolved
here — defaults filled in, aliases mapped — so no template has to guess.

The canonical layout is::

    [book]
    title    = "A Short Manual"
    slug     = "a-short-manual"
    imprint  = "Example Press"
    template = "prose"
    content  = "content.md"

    [print]
    cover_bg = "101014"

    [theme]
    paper = "f4efe4"
    ink   = "1a1a1a"

Only ``book.title`` and ``book.slug`` are required; everything else has a default.
An older layout that nests metadata under ``[meta]`` and calls the theme ``[skin]`` is
also accepted, so existing projects keep building unchanged.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace

CONFIG_NAMES = ("book.toml", "manifesto.toml")

#: Trims used when a book does not declare any. A 5x8 perfect-bound paperback and a
#: 5.5x8.5 case-bound hardcover, the two most common print-on-demand sizes.
DEFAULT_TRIMS = [
    {"name": "paperback", "width": 5.0, "height": 8.0, "binding": "wrap",
     "spine_per_page": 0.002347},
    {"name": "hardcover", "width": 5.5, "height": 8.5, "binding": "case",
     "spine_per_page": 0.002252, "spine_extra": 0.06, "wrap": 0.625, "hinge": 0.375},
]

TEMPLATE_ALIASES = {"bible": "verse", "axiom": "atlas", "plate": "prose"}


class ConfigError(Exception):
    """A book's config is missing or malformed."""


@dataclass(frozen=True)
class Trim:
    """One printed size, and how its cover is assembled.

    ``binding="wrap"`` is a flat wrap — back panel, spine, front panel — as used for
    perfect-bound paperbacks. ``binding="case"`` is a hardcover case wrap, which adds
    a turn-in (``wrap``), a hinge either side of the spine, and a thicker spine.
    """

    name: str
    width: float
    height: float
    binding: str = "wrap"
    spine_per_page: float = 0.002347
    spine_extra: float = 0.0
    wrap: float = 0.625
    hinge: float = 0.375
    bleed: float = 0.125

    def spine(self, pages: int) -> float:
        """Spine thickness in inches for a given page count."""
        return pages * self.spine_per_page + self.spine_extra


@dataclass(frozen=True)
class Theme:
    """The colour set a book is printed and rendered in.

    ``accent`` carries headings and rules; ``accent2`` carries ornament and the frame.
    The remaining fields are derived from those two unless given explicitly, so a
    minimal theme is four colours.
    """

    paper: str = "f4efe4"
    ink: str = "1a1a1a"
    accent: str = "7a5a1e"
    accent2: str = "a8802e"
    mute: str = "6f6a60"
    rule: str = ""
    badge: str = ""
    faint: str = ""
    mono_ink: str = "0e2a52"
    caption_ink: str = ""
    backdrop: str = "12100e"

    def __post_init__(self):
        # frozen dataclass: fill the derived colours through object.__setattr__
        for name, fallback in (("rule", self.accent), ("badge", self.paper),
                               ("faint", self.accent2), ("caption_ink", self.mute)):
            if not getattr(self, name):
                object.__setattr__(self, name, fallback)


@dataclass
class Book:
    """A single edition of a single book, fully resolved."""

    dir: str
    slug: str
    title: str
    subtitle: str = ""
    tagline: str = ""
    imprint: str = ""
    template: str = "prose"
    content: str = ""
    title_lines: list[str] = field(default_factory=list)
    edition: int = 1
    title_mono: bool = False

    series_label: str = ""
    volume: int | None = None

    theme: Theme = field(default_factory=Theme)
    trims: list[Trim] = field(default_factory=list)
    primary_trim: str = ""

    bleed: float = 0.125
    min_pages: int = 24
    cover_bg: str = "101014"
    declared_pages: int = 24

    isbn: dict = field(default_factory=dict)
    epigraph: dict = field(default_factory=dict)
    description: str = ""
    figures: dict = field(default_factory=dict)   # declared [[figure]] tables, by name
    graphs: str = ""                              # a figure module, for computed artwork
    closing: str = "Here ends {title}."

    raw: dict = field(default_factory=dict)

    # -- derived paths ----------------------------------------------------
    @property
    def art_dir(self) -> str:
        return os.path.join(self.dir, "art")

    @property
    def dist_dir(self) -> str:
        return os.path.join(self.dir, "dist")

    @property
    def content_path(self) -> str:
        return os.path.join(self.dir, self.content)

    def primary(self) -> Trim:
        for t in self.trims:
            if t.name == self.primary_trim:
                return t
        return self.trims[0]

    def output_name(self, kind: str, trim: Trim, ext: str) -> str:
        """``<slug>-<kind>.<ext>`` for the primary trim, ``…-<trim>.<ext>`` for the rest.

        Keeps the primary edition's filenames stable when further trims are added.
        """
        stem = f"{self.slug}-{kind}" if trim.name == self.primary().name \
            else f"{self.slug}-{kind}-{trim.name}"
        return f"{stem}.{ext}"

    def closing_line(self) -> str:
        return self.closing.format(title=self.title)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def find_config(directory: str) -> str | None:
    """Return the config file inside *directory*, or None if there is not one."""
    for name in CONFIG_NAMES:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    return None


def _theme_from(raw: dict) -> Theme:
    src = raw.get("theme") or raw.get("skin") or {}
    # 'bronze'/'bronze2' were the older names for the two accents
    mapped = {
        "paper": src.get("paper"), "ink": src.get("ink"),
        "accent": src.get("accent") or src.get("bronze"),
        "accent2": src.get("accent2") or src.get("bronze2"),
        "mute": src.get("mute"), "rule": src.get("rule"), "badge": src.get("badge"),
        "faint": src.get("faint"), "mono_ink": src.get("mono_ink"),
        "caption_ink": src.get("caption_ink"), "backdrop": src.get("backdrop"),
    }
    return Theme(**{k: v.lstrip("#") for k, v in mapped.items() if v})


def _trims_from(raw: dict, bleed: float) -> list[Trim]:
    printing = raw.get("print") or {}
    declared = printing.get("trims") or DEFAULT_TRIMS
    allowed = set(Trim.__dataclass_fields__)
    out = []
    for t in declared:
        missing = {"name", "width", "height"} - set(t)
        if missing:
            raise ConfigError(
                f"[[print.trims]] is missing {', '.join(sorted(missing))}")
        unknown = set(t) - allowed
        if unknown:
            raise ConfigError(
                f"[[print.trims]] '{t['name']}' has unknown key(s) "
                f"{', '.join(sorted(unknown))}; allowed: {', '.join(sorted(allowed))}")
        out.append(Trim(**{"bleed": bleed, **t}))
    return out


def _figures_from(raw: dict) -> dict:
    """Index the ``[[figure]]`` tables by name."""
    out = {}
    for spec in raw.get("figure", []):
        name = spec.get("name")
        if not name:
            raise ConfigError("every [[figure]] needs a name")
        if name in out:
            raise ConfigError(f"two figures are named '{name}'")
        out[name] = spec
    return out


def load(directory: str) -> Book:
    """Load the book in *directory*. Raises :class:`ConfigError` if there is none."""
    path = find_config(directory)
    if path is None:
        raise ConfigError(f"no {' or '.join(CONFIG_NAMES)} in {directory}")
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    book = raw.get("book") or raw.get("meta")
    if not book:
        raise ConfigError(f"{path}: needs a [book] table")

    title = book.get("title") or book.get("manifesto")
    if not title:
        raise ConfigError(f"{path}: [book] needs a title")
    slug = book.get("slug")
    if not slug:
        raise ConfigError(f"{path}: [book] needs a slug")

    printing = raw.get("print") or book.get("print") or {}
    series = raw.get("series") or {}
    bleed = float(printing.get("bleed", 0.125))
    trims = _trims_from({"print": printing}, bleed)

    template = book.get("template", "prose")
    template = TEMPLATE_ALIASES.get(template, template)

    content = (book.get("content") or book.get("content_file")
               or book.get("proverbs_file") or "")

    return Book(
        dir=directory,
        slug=slug,
        title=title,
        subtitle=book.get("subtitle", ""),
        tagline=book.get("tagline", ""),
        imprint=book.get("imprint", ""),
        template=template,
        content=content,
        title_lines=book.get("title_lines") or [title.upper()],
        edition=int(book.get("edition", 1)),
        title_mono=bool(book.get("title_mono", False)),
        series_label=series.get("label") or book.get("series_label", ""),
        volume=series.get("volume", book.get("volume")),
        theme=_theme_from(raw),
        trims=trims,
        primary_trim=printing.get("primary_trim") or trims[0].name,
        bleed=bleed,
        min_pages=int(printing.get("min_pages", 24)),
        cover_bg=str(printing.get("cover_bg", "101014")).lstrip("#"),
        declared_pages=int(printing.get("pages", 24)),
        isbn=raw.get("isbn") or book.get("isbn") or {},
        epigraph=raw.get("epigraph") or {},
        description=(raw.get("description") or {}).get("body", ""),
        figures=_figures_from(raw),
        graphs=book.get("figures") or book.get("graphs", ""),
        closing=book.get("closing", "Here ends {title}."),
        raw=raw,
    )


def discover(root: str) -> list[str]:
    """Every directory under *root* that holds a book config, sorted by path."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in ("dist", "art", "__pycache__")]
        if any(name in filenames for name in CONFIG_NAMES):
            found.append(dirpath)
    return sorted(found)
