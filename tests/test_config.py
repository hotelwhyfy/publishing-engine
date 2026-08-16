import textwrap

import pytest

from publishing_engine import config


def write(tmp_path, body, name="book.toml"):
    (tmp_path / name).write_text(textwrap.dedent(body))
    return str(tmp_path)


MINIMAL = """
    [book]
    title = "A Short Manual"
    slug  = "short-manual"
"""


def test_minimal_book_gets_defaults(tmp_path):
    book = config.load(write(tmp_path, MINIMAL))
    assert book.title == "A Short Manual"
    assert book.template == "prose"
    assert book.title_lines == ["A SHORT MANUAL"]
    assert [t.name for t in book.trims] == ["paperback", "hardcover"]
    assert book.primary().name == "paperback"
    assert book.min_pages == 24


def test_missing_config_is_reported(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load(str(tmp_path))


def test_title_and_slug_are_required(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load(write(tmp_path, '[book]\nslug = "x"\n'))
    with pytest.raises(config.ConfigError):
        config.load(write(tmp_path, '[book]\ntitle = "x"\n'))


def test_legacy_layout_still_loads(tmp_path):
    """The older [meta]/[skin] shape, with its own key names."""
    book = config.load(write(tmp_path, """
        [meta]
        manifesto    = "Old Shape"
        slug         = "old-shape"
        template     = "bible"
        series_label = "A Series"
        volume       = 3
        content_file = "content.md"

        [meta.print]
        cover_bg = "112233"
        pages    = 40

        [meta.isbn]
        paperback = "978-x"

        [skin]
        paper   = "ffffff"
        bronze  = "aa0000"
        bronze2 = "00aa00"
    """))
    assert book.title == "Old Shape"
    assert book.template == "verse"          # 'bible' is an alias
    assert book.series_label == "A Series"
    assert book.volume == 3
    assert book.content == "content.md"
    assert book.cover_bg == "112233"
    assert book.declared_pages == 40
    assert book.isbn["paperback"] == "978-x"
    assert book.theme.accent == "aa0000"     # bronze -> accent
    assert book.theme.accent2 == "00aa00"


def test_series_table_is_optional(tmp_path):
    book = config.load(write(tmp_path, MINIMAL))
    assert book.series_label == ""
    assert book.volume is None


def test_custom_trims_replace_the_defaults(tmp_path):
    book = config.load(write(tmp_path, MINIMAL + """
        [[print.trims]]
        name = "pocket"
        width = 4.25
        height = 6.87

        [[print.trims]]
        name = "large-print"
        width = 6.0
        height = 9.0
    """))
    assert [t.name for t in book.trims] == ["pocket", "large-print"]
    assert book.primary().name == "pocket"


def test_primary_trim_can_be_chosen(tmp_path):
    book = config.load(write(tmp_path, MINIMAL + '\n[print]\nprimary_trim = "hardcover"\n'))
    assert book.primary().name == "hardcover"


def test_output_names_keep_the_primary_bare(tmp_path):
    book = config.load(write(tmp_path, MINIMAL))
    paperback, hardcover = book.trims
    assert book.output_name("interior", paperback, "pdf") == "short-manual-interior.pdf"
    assert book.output_name("interior", hardcover, "pdf") == "short-manual-interior-hardcover.pdf"


def test_theme_derives_the_colours_it_is_not_given():
    theme = config.Theme(accent="112233", accent2="445566", paper="ffffff", mute="777777")
    assert theme.rule == "112233"       # falls back to accent
    assert theme.faint == "445566"      # falls back to accent2
    assert theme.badge == "ffffff"      # falls back to paper
    assert theme.caption_ink == "777777"


def test_theme_keeps_explicit_colours():
    theme = config.Theme(accent="112233", rule="abcdef")
    assert theme.rule == "abcdef"


def test_hashes_are_stripped_from_colours(tmp_path):
    book = config.load(write(tmp_path, MINIMAL + '\n[theme]\npaper = "#fafafa"\n'))
    assert book.theme.paper == "fafafa"


def test_spine_grows_with_the_page_count():
    trim = config.Trim(name="p", width=5, height=8, spine_per_page=0.002347)
    assert trim.spine(24) == pytest.approx(0.056328)
    case = config.Trim(name="h", width=5.5, height=8.5,
                       spine_per_page=0.002252, spine_extra=0.06)
    assert case.spine(24) == pytest.approx(0.114048)


def test_discover_finds_books_and_skips_output(tmp_path):
    (tmp_path / "one").mkdir()
    write(tmp_path / "one", MINIMAL)
    (tmp_path / "one" / "dist").mkdir()
    write(tmp_path / "one" / "dist", MINIMAL)      # must not be picked up
    (tmp_path / "two").mkdir()
    write(tmp_path / "two", MINIMAL, name="manifesto.toml")

    found = config.discover(str(tmp_path))
    assert found == [str(tmp_path / "one"), str(tmp_path / "two")]
