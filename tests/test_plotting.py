import math

import pytest

from publishing_engine import plotting
from publishing_engine.config import Theme
from publishing_engine.plotting import draw, expr, scale

THEME = Theme(paper="ffffff", ink="000000", accent="112233", accent2="445566",
              mute="777777")


# -- expressions -----------------------------------------------------------

def test_arithmetic():
    assert expr.compile_expr("2 * x + 1")(3) == 7
    assert expr.compile_expr("(x^2 - 1)/(x - 1)")(3) == 4
    assert expr.compile_expr("-x")(2) == -2


def test_caret_is_exponentiation_not_xor():
    assert expr.compile_expr("2^10")(0) == 1024


def test_functions_and_constants():
    assert expr.compile_expr("sin(x)")(0) == 0
    assert expr.compile_expr("sqrt(x)")(9) == 3
    assert expr.compile_expr("ln(x)")(math.e) == pytest.approx(1)
    assert expr.evaluate("pi") == pytest.approx(math.pi)


def test_piecewise():
    absolute = expr.compile_expr("x if x > 0 else -x")
    assert absolute(3) == 3 and absolute(-3) == 3


@pytest.mark.parametrize("source", [
    "__import__('os').system('echo hi')",
    "open('/etc/passwd')",
    "x.__class__",
    "[1, 2, 3]",
    "lambda: 1",
    "unknown_name",
    "unknown_function(x)",
    "'a string'",
])
def test_unsafe_expressions_are_refused(source):
    with pytest.raises(expr.ExpressionError):
        expr.compile_expr(source)(1.0)


def test_malformed_expression_names_itself():
    with pytest.raises(expr.ExpressionError) as caught:
        expr.compile_expr("2 +* 3")
    assert "2 +* 3" in str(caught.value)


def test_as_number_takes_numbers_or_expressions():
    assert expr.as_number(2) == 2.0
    assert expr.as_number("pi/2") == pytest.approx(math.pi / 2)


# -- scales ----------------------------------------------------------------

def test_ticks_land_on_round_numbers():
    assert scale.nice_ticks(0, 10, 5) == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    for tick in scale.nice_ticks(0, 1, 5):
        assert round(tick * 100) % 5 == 0


def test_ticks_survive_a_degenerate_range():
    assert scale.nice_ticks(1, 1) == [1]
    assert scale.nice_ticks(float("nan"), 1) == []


def test_scale_maps_and_inverts():
    s = scale.Scale(0, 10, 0, 100)
    assert s(0) == 0 and s(10) == 100 and s(5) == 50
    flipped = scale.Scale(0, 10, 0, 100, invert=True)
    assert flipped(0) == 100 and flipped(10) == 0


def test_tick_labels_are_terse():
    assert scale.format_tick(3.0) == "3"
    assert scale.format_tick(0.5, 0.5) == "0.5"


# -- rendering -------------------------------------------------------------

def test_a_curve_renders_a_path():
    svg = plotting.render({"name": "f", "x": [-2, 2], "curve": [{"of": "x^2"}]}, THEME)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "<path" in svg


def test_a_hole_breaks_the_curve_and_marks_it():
    svg = plotting.render({"name": "f", "x": [-1, 3], "y": [-1, 5],
                           "curve": [{"of": "(x^2-1)/(x-1)", "holes": [1]}]}, THEME)
    assert svg.count("<path") >= 2      # one run either side of the hole
    assert "<circle" in svg             # the open circle at the limit


def test_bars_render_rects_and_categories_render_labels():
    svg = plotting.render({"name": "c", "kind": "chart", "x": ["a", "b"],
                           "series": [{"type": "bar", "values": [1, 2]}]}, THEME)
    assert svg.count("<rect") >= 3      # background plus two bars
    assert ">a</text>" in svg and ">b</text>" in svg


@pytest.mark.parametrize("series_type", ["bar", "line", "scatter", "step"])
def test_every_series_type_draws_something(series_type):
    svg = plotting.render({"name": "c", "kind": "chart",
                           "series": [{"type": series_type, "values": [1, 3, 2]}]}, THEME)
    assert len(svg) > 400


def test_area_shading_and_tangent_and_notes():
    svg = plotting.render({
        "name": "f", "x": [0, 3],
        "curve": [{"of": "x^2"}],
        "area": [{"of": "x^2", "from": 0.5, "to": 2}],
        "tangent": [{"of": "x^2", "at": 1.5}],
        "point": [{"at": [1, 1], "style": "open"}],
        "line": [{"y": 2, "label": "y = 2"}],
        "note": [{"at": [1, 3], "text": "here"}],
    }, THEME)
    assert ">here</text>" in svg and ">y = 2</text>" in svg


def test_the_book_theme_reaches_the_figure():
    svg = plotting.render({"name": "f", "curve": [{"of": "x"}]}, THEME)
    assert "#112233" in svg          # the accent drew the curve
    assert "#ffffff" in svg          # the paper drew the ground


def test_a_label_becomes_a_legend_entry():
    svg = plotting.render({"name": "f", "curve": [{"of": "x", "label": "the line"}]}, THEME)
    assert ">the line</text>" in svg


def test_text_is_never_a_real_italic():
    """The rasteriser mis-spaces italic f, and labels are full of them."""
    svg = plotting.render({"name": "f", "xlabel": "f(x)", "ylabel": "y",
                           "curve": [{"of": "x"}]}, THEME)
    assert "font-style" not in svg
    assert "skewX" in svg            # slanted with a transform instead


def test_aspect_defaults_and_overrides():
    assert plotting.aspect({}) == 1.6
    assert plotting.aspect({"aspect": 2.0}) == 2.0
    assert plotting.aspect({"aspect": "nonsense"}) == 1.6


def test_unknown_kind_is_refused():
    with pytest.raises(draw.FigureError):
        plotting.render({"name": "f", "kind": "sculpture"}, THEME)


def test_a_curve_needs_an_expression():
    with pytest.raises(draw.FigureError):
        plotting.render({"name": "f", "curve": [{"label": "no expression"}]}, THEME)


def test_a_chart_needs_a_series():
    with pytest.raises(draw.FigureError):
        plotting.render({"name": "c", "kind": "chart", "series": []}, THEME)


def test_an_asymptote_does_not_join_across_itself():
    """1/x must not be drawn as one stroke leaping from -inf to +inf through zero."""
    svg = plotting.render({"name": "f", "x": [-3, 3], "y": [-6, 6],
                           "curve": [{"of": "1/x"}]}, THEME)
    assert svg.count("<path") >= 2


def test_auto_range_ignores_the_blow_up():
    """A curve with an asymptote should still frame its interesting part."""
    spec = {"name": "f", "x": [-3, 3], "curve": [{"of": "1/x"}]}
    svg = plotting.render(spec, THEME)
    assert "<svg" in svg             # renders at all rather than scaling to infinity
