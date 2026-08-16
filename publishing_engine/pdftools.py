"""Post-processing that keeps the output acceptable to print services.

reportlab writes an unused Helvetica into every page's font resources *and* references
that tag from the content stream. Deleting the resource leaves a dangling reference —
checkers report an unknown font tag, and some print processors reject the file. So
instead of deleting it, every unembedded entry is pointed at a font object that *is*
embedded. The tag then resolves to a real font:

* every font reports as embedded,
* no dangling references remain,
* nothing visible changes, because nothing actually draws with that tag.

Usually there is an embedded font already in the document to point at. A cover wrap is
the exception — it is all artwork and sets no type of its own — so for those a minimal
donor document is generated and its embedded font copied in.
"""
from __future__ import annotations

import io

import pikepdf

_FONT_FILE_KEYS = ("/FontFile", "/FontFile2", "/FontFile3")


def _is_embedded(font):
    descriptor = font.get("/FontDescriptor")
    if descriptor is not None and any(k in descriptor for k in _FONT_FILE_KEYS):
        return True
    if font.get("/Subtype") == "/Type0":
        for descendant in (font.get("/DescendantFonts") or []):
            dd = descendant.get("/FontDescriptor")
            if dd is not None and any(k in dd for k in _FONT_FILE_KEYS):
                return True
    return False


def _first_embedded(pdf):
    for page in pdf.pages:
        fonts = (page.get("/Resources") or {}).get("/Font")
        for _, font in (fonts or {}).items():
            if _is_embedded(font):
                return font
    return None


def _donor():
    """A throwaway one-page PDF whose only content is type set in an embedded font."""
    from reportlab.pdfgen import canvas

    from . import fonts

    fonts.register()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(12, 12))
    c.setFont(fonts.SERIF, 6)
    c.drawString(1, 1, ".")
    c.save()
    buffer.seek(0)
    return pikepdf.open(buffer)


def embed_fonts(path) -> int:
    """Alias unembedded font entries in *path* to an embedded one. Returns how many."""
    pdf = pikepdf.open(path, allow_overwriting_input=True)
    donor = None
    try:
        replacement = _first_embedded(pdf)
        if replacement is None:
            # nothing in this document is embedded — bring a font in from outside
            donor = _donor()
            source = _first_embedded(donor)
            replacement = pdf.copy_foreign(source) if source is not None else None

        aliased = 0
        if replacement is not None:
            for page in pdf.pages:
                fonts = (page.get("/Resources") or {}).get("/Font")
                if not fonts:
                    continue
                for key in list(fonts.keys()):
                    if not _is_embedded(fonts[key]):
                        fonts[key] = replacement
                        aliased += 1
        pdf.save(path)
    finally:
        pdf.close()
        if donor is not None:
            donor.close()
    return aliased


def embed_fonts_in(paths) -> int:
    return sum(embed_fonts(p) for p in paths)
