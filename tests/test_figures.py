"""Where a figure comes from when a book has both a declaration and a module."""
import textwrap

import pytest

from publishing_engine import config, figures


def book_with(tmp_path, body, module=None):
    (tmp_path / "book.toml").write_text(textwrap.dedent(body))
    if module is not None:
        (tmp_path / "figures.py").write_text(textwrap.dedent(module))
    return config.load(str(tmp_path))


DECLARED = """
    [book]
    title = "T"
    slug  = "t"

    [[figure]]
    name = "one"
    [[figure.curve]]
    of = "x"
"""

MODULE = """
    def figure_svg(name):
        return f'<svg viewBox="0 0 10 10"><title>{name} from the module</title></svg>'

    def aspect(name):
        return 2.5
"""


def test_a_declared_figure_is_drawn_by_the_engine(tmp_path):
    book = book_with(tmp_path, DECLARED)
    source = figures.for_book(book)
    assert "<path" in source.svg("one")
    assert source.aspect("one") == 1.6


def test_a_module_supplies_figures_when_named(tmp_path):
    book = book_with(tmp_path, """
        [book]
        title = "T"
        slug  = "t"
        figures = "figures.py"
    """, MODULE)
    source = figures.for_book(book)
    assert "from the module" in source.svg("anything")
    assert source.aspect("anything") == 2.5


def test_a_declaration_wins_over_a_module_of_the_same_name(tmp_path):
    book = book_with(tmp_path, DECLARED.replace(
        'slug  = "t"', 'slug  = "t"\nfigures = "figures.py"'), MODULE)
    source = figures.for_book(book)
    assert "from the module" not in source.svg("one")     # the declaration drew it
    assert "from the module" in source.svg("other")       # the module covered the rest


def test_the_older_module_function_name_still_works(tmp_path):
    book = book_with(tmp_path, """
        [book]
        title = "T"
        slug  = "t"
        figures = "figures.py"
    """, """
        def graph_svg(name):
            return "<svg/>"

        def aspect(name):
            return 1.0
    """)
    assert figures.for_book(book).svg("x") == "<svg/>"


def test_a_module_missing_the_interface_is_reported(tmp_path):
    book = book_with(tmp_path, """
        [book]
        title = "T"
        slug  = "t"
        figures = "figures.py"
    """, "def something_else():\n    pass\n")
    with pytest.raises(figures.FigureError):
        figures.for_book(book).svg("x")


def test_asking_for_a_figure_a_book_does_not_have(tmp_path):
    book = book_with(tmp_path, "[book]\ntitle = 'T'\nslug = 't'\n")
    with pytest.raises(figures.FigureError):
        figures.for_book(book).svg("missing")


def test_figures_are_indexed_by_name(tmp_path):
    book = book_with(tmp_path, DECLARED)
    assert list(book.figures) == ["one"]


def test_a_figure_without_a_name_is_refused(tmp_path):
    (tmp_path / "book.toml").write_text(
        "[book]\ntitle='T'\nslug='t'\n\n[[figure]]\nkind='plot'\n")
    with pytest.raises(config.ConfigError):
        config.load(str(tmp_path))


def test_two_figures_may_not_share_a_name(tmp_path):
    (tmp_path / "book.toml").write_text(
        "[book]\ntitle='T'\nslug='t'\n\n[[figure]]\nname='a'\n\n[[figure]]\nname='a'\n")
    with pytest.raises(config.ConfigError):
        config.load(str(tmp_path))
