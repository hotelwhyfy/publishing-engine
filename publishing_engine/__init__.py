"""A small publishing engine: one config file in, print-ready book out.

A book is a directory holding a config file, its content, and its cover art. From that
the engine produces a print-ready interior PDF for every trim it is issued at, a cover
wrap sized to the real page count of each, a self-contained reading HTML, and the plain
text of its catalogue listing.

    from publishing_engine import build
    result = build("books/a-short-manual")

Templates decide how content is set on the page — see :mod:`publishing_engine.templates`.
Nothing about any particular book lives in here: the title, the colours, the trims, the
figures and the words all come from the book's own directory.
"""

__version__ = "0.1.0"

from .builder import build, build_all  # noqa: E402
from .config import Book, ConfigError, Theme, Trim, discover, load  # noqa: E402

__all__ = ["build", "build_all", "load", "discover",
           "Book", "Theme", "Trim", "ConfigError", "__version__"]
