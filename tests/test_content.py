import textwrap

from publishing_engine import markup, numbers, palette
from publishing_engine.sources import prose, verse


def content(tmp_path, body, name="content.md"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip("\n"))
    return str(path)


# -- prose -----------------------------------------------------------------

def test_prose_reads_every_block_type(tmp_path):
    blocks = prose.parse(content(tmp_path, """
        // a comment, ignored
        # A Heading
        First line
        and its continuation.

        Second paragraph.

        ## A Subheading
        > A pull quote
        ---
        ![](art/plate.svg)
        ![A caption](art/figure.svg)
    """))
    assert [b["type"] for b in blocks] == [
        "heading", "p", "p", "subheading", "quote", "break", "image", "image"]
    assert blocks[1]["text"] == "First line and its continuation."
    assert blocks[0]["text"] == "A Heading"
    assert blocks[4]["text"] == "A pull quote"


def test_empty_caption_means_a_full_page_plate(tmp_path):
    blocks = prose.parse(content(tmp_path, "![](art/a.svg)\n"))
    assert blocks[0]["full"] is True
    assert blocks[0]["src"] == "art/a.svg"


def test_a_caption_means_an_inline_figure(tmp_path):
    blocks = prose.parse(content(tmp_path, "![Some words](art/a.svg)\n"))
    assert blocks[0]["full"] is False
    assert blocks[0]["caption"] == "Some words"


def test_full_can_be_forced_alongside_a_caption(tmp_path):
    blocks = prose.parse(content(tmp_path, "![Some words](art/a.svg){full}\n"))
    assert blocks[0]["full"] is True


def test_inline_can_be_forced_without_a_caption(tmp_path):
    blocks = prose.parse(content(tmp_path, "![](art/a.svg){inline}\n"))
    assert blocks[0]["full"] is False


# -- verse -----------------------------------------------------------------

def test_verse_groups_entries_under_sections(tmp_path):
    sections = verse.parse(content(tmp_path, """
        // ignored
        # First Section
        One.
        Two.
        # Second Section
        Three.
    """))
    assert [s["name"] for s in sections] == ["First Section", "Second Section"]
    assert sections[0]["entries"] == ["One.", "Two."]
    assert sections[1]["entries"] == ["Three."]


def test_verse_allows_entries_before_any_heading(tmp_path):
    sections = verse.parse(content(tmp_path, "Loose one.\n# Named\nInside.\n"))
    assert sections[0]["name"] is None
    assert sections[0]["entries"] == ["Loose one."]


def test_verse_drops_empty_sections(tmp_path):
    sections = verse.parse(content(tmp_path, "# Empty\n# Full\nAn entry.\n"))
    assert [s["name"] for s in sections] == ["Full"]


# -- markup ----------------------------------------------------------------

def test_markup_to_html():
    out = markup.to_html("**bold** *italic* `mono` x^{2} a_{i}")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out
    assert "<code>mono</code>" in out
    assert "<sup>2</sup>" in out and "<sub>i</sub>" in out


def test_markup_to_reportlab():
    out = markup.to_reportlab("**bold** *italic* `mono` x^{2}")
    assert "<b>bold</b>" in out
    assert "<i>italic</i>" in out
    assert "<super>2</super>" in out
    assert 'font name="BookMono"' in out


def test_markup_escapes_before_it_marks_up():
    assert markup.to_html("a < b & c") == "a &lt; b &amp; c"


def test_pdf_swaps_glyphs_the_serif_faces_lack():
    assert markup.to_reportlab("∬ f") .startswith("∫∫")
    assert "→" in markup.to_reportlab("a ⇒ b")
    assert "⇒" in markup.to_html("a ⇒ b")      # HTML keeps the original


def test_plain_strips_markup():
    assert markup.plain("**a** *b* `c`") == "a b c"


def test_paragraphs_split_on_blank_lines():
    assert markup.paragraphs("one\nline\n\ntwo\n") == ["one\nline", "two"]


# -- numbers and colour ----------------------------------------------------

def test_numbers_in_words():
    assert numbers.in_words(1) == "one"
    assert numbers.in_words(7) == "seven"
    assert numbers.in_words(21) == "twenty-one"
    assert numbers.in_words(30) == "thirty"
    assert numbers.in_words(140) == "140"


def test_roman_numerals():
    assert numbers.roman(1) == "I"
    assert numbers.roman(4) == "IV"
    assert numbers.roman(1987) == "MCMLXXXVII"


def test_palette_helpers():
    assert palette.rgb("#a8802e") == (168, 128, 46)
    assert palette.rgb("abc") == (170, 187, 204)
    assert palette.rgba("000000", 0.5) == "rgba(0,0,0,0.5)"
    assert palette.shade("808080", 2) == "ffffff"      # clamps at the top
    assert palette.shade("808080", 0) == "000000"
    assert "radial-gradient" in palette.backdrop("101010")
