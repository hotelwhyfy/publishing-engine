"""End-to-end: build the example book and check what came out."""
import os
import shutil

import pytest

from publishing_engine import builder, config, fonts

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "examples", "sample-book")

pytest.importorskip("reportlab")
pytest.importorskip("cairosvg")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("book")
    target = workspace / "sample-book"
    shutil.copytree(EXAMPLE, target)
    shutil.rmtree(target / "dist", ignore_errors=True)
    return builder.build(str(target)), str(target)


def test_it_builds_a_pdf_for_every_trim(built):
    result, target = built
    names = {os.path.basename(p) for p in result.pdfs}
    assert "kitchen-garden-interior.pdf" in names
    assert "kitchen-garden-interior-hardcover.pdf" in names


def test_it_builds_a_cover_for_every_trim(built):
    result, _ = built
    names = {os.path.basename(p) for p in result.pdfs}
    assert "kitchen-garden-cover-wrap.pdf" in names
    assert "kitchen-garden-cover-wrap-hardcover.pdf" in names


def test_page_counts_meet_the_minimum_and_are_even(built):
    result, _ = built
    assert set(result.pages) == {"paperback", "hardcover"}
    for count in result.pages.values():
        assert count >= 24
        assert count % 2 == 0


def test_it_writes_reading_html(built):
    result, _ = built
    assert os.path.exists(result.html)
    html = open(result.html, encoding="utf-8").read()
    assert "The Kitchen Garden" in html
    assert "<blockquote>" in html          # the pull quote survived
    assert "<figure>" in html              # and the inline figure
    assert "../art/the-bed.svg" in html    # rewritten relative to dist/


def test_a_declared_figure_is_drawn_into_both_editions(built):
    """The example declares a chart in its config and refers to it from content."""
    result, target = built
    html = open(result.html, encoding="utf-8").read()
    assert "<svg" in html                  # embedded, not linked
    assert "sown all at once" in html      # the series label the config gave it

    pymupdf = pytest.importorskip("pymupdf")
    interior = next(p for p in result.pdfs if p.endswith("kitchen-garden-interior.pdf"))
    document = pymupdf.open(interior)
    assert sum(len(page.get_images()) for page in document) >= 2  # the SVG and the chart


def test_it_writes_the_listing(built):
    result, _ = built
    text = open(result.description, encoding="utf-8").read()
    assert "THE KITCHEN GARDEN" in text
    assert "Working Notes · Volume One" in text
    assert "paperback (5 x 8 in)" in text
    assert "ISBN: forthcoming" in text


def test_the_scratch_directory_is_cleaned_up(built):
    _, target = built
    assert not os.path.exists(os.path.join(target, "dist", "_render"))


def test_every_font_is_embedded(built):
    result, _ = built
    pymupdf = pytest.importorskip("pymupdf")
    for path in result.pdfs:
        document = pymupdf.open(path)
        for page in document:
            for font in page.get_fonts():
                # a subset prefix ("AAAAAA+Name") is what an embedded font looks like
                assert "+" in font[3], f"{font[3]} is not embedded in {path}"


def test_page_size_includes_the_bleed(built):
    result, _ = built
    pymupdf = pytest.importorskip("pymupdf")
    interior = next(p for p in result.pdfs if p.endswith("kitchen-garden-interior.pdf"))
    rect = pymupdf.open(interior)[0].rect
    # 5 x 8 trim, 0.125 bleed: 5.125 x 8.25 inches at 72pt
    assert round(rect.width, 1) == 369.0
    assert round(rect.height, 1) == 594.0


def test_cover_width_accounts_for_the_spine(built):
    result, target = built
    pymupdf = pytest.importorskip("pymupdf")
    book = config.load(target)
    trim = book.primary()
    wrap = next(p for p in result.pdfs if p.endswith("kitchen-garden-cover-wrap.pdf"))
    rect = pymupdf.open(wrap)[0].rect
    expected = (2 * trim.width + trim.spine(result.pages["paperback"]) + 2 * trim.bleed) * 72
    assert rect.width == pytest.approx(expected, abs=0.01)


def test_covers_can_be_skipped(tmp_path):
    target = tmp_path / "sample-book"
    shutil.copytree(EXAMPLE, target)
    shutil.rmtree(target / "dist", ignore_errors=True)
    result = builder.build(str(target), covers=False, html=False)
    assert all("cover-wrap" not in p for p in result.pdfs)
    assert result.html == ""


def test_fonts_register_without_error():
    fonts.register()
    size, tracking = fonts.fit_tracking("A VERY LONG HEADING INDEED", fonts.SERIF_B,
                                        13, 3.0, max_width=100)
    assert size <= 13 and tracking <= 3.0


def test_long_lines_are_wrapped_to_the_width():
    fonts.register()
    text = "a subtitle long enough that it could never fit on one line of a small page"
    lines = fonts.wrap_lines(text, fonts.SERIF_I, 14.5, 240)
    assert len(lines) > 1
    assert " ".join(lines) == text
