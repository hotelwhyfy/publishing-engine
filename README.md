# publishing-engine

Build print-ready books from a directory and a config file.

Point it at a folder holding your text, your cover art and a `book.toml`, and it
produces a print-ready interior PDF for every trim you issue the book at, a cover wrap
sized to each interior's real page count, a self-contained reading HTML, and the plain
text of the catalogue listing.

```
publish build my-book

=== A Short Manual ===
  4 PDF(s) (paperback 34 pp, hardcover 28 pp), fonts embedded
  short-manual-interior.html
```

Nothing about any particular book lives in the engine. The title, the colours, the
trims, the figures and the words all come from the book's own directory — so books are
kept in their own repository and this one stays a tool.

---

## Install

```bash
pip install -e .          # from a checkout
pip install -e ".[dev]"   # with pytest and a PDF rasteriser, for the tests
```

Python 3.11 or newer. The dependencies are `reportlab` (PDF), `cairosvg` (SVG art),
`pikepdf` (font hygiene) and `pillow`.

On macOS, cairosvg needs to find libcairo. If it cannot:

```bash
mkdir -p ~/lib && ln -sf /opt/homebrew/lib/libcairo.2.dylib ~/lib/
```

---

## Quick start

```bash
publish new my-book       # copy the worked example
cd my-book
$EDITOR book.toml         # title, imprint, colours, trims
$EDITOR content.md        # the book
publish build .
```

Everything lands in `my-book/dist/`.

---

## A book on disk

```
my-book/
  book.toml          all metadata: title, theme, trims, ISBNs, listing copy
  content.md         the text
  art/
    front-cover.svg  cover panels (optional — no art, no covers)
    back-cover.svg
    figure-one.svg   anything the content refers to
  dist/              everything the engine produces
```

The engine finds books by looking for `book.toml`, so a repository can hold as many as
you like at any depth:

```bash
publish list                    # what is here
publish build                   # all of them
publish build short-manual      # by slug
publish build series-two/       # by path fragment
```

Point `--root` at wherever the books are kept:

```bash
publish build --root ../my-books
```

---

## book.toml

Only `title` and `slug` are required. Everything below shows its default.

```toml
[book]
title       = "A Short Manual"        # required
slug        = "short-manual"          # required — names every output file
subtitle    = ""
tagline     = ""                      # one line, for the listing and the atlas title page
imprint     = ""                      # publisher, set on the title page and colophon
template    = "prose"                 # prose | verse | atlas
content     = "content.md"
title_lines = ["A SHORT MANUAL"]      # the title as broken across the title page
edition     = 1
closing     = "Here ends {title}."    # the colophon line
figures     = ""                      # atlas only; see below

[series]                              # optional; omit entirely for a standalone book
label  = "Working Notes"
volume = 1

[print]
bleed        = 0.125                  # inches, on every edge
min_pages    = 24                     # pad with blanks up to this, and to an even count
cover_bg     = "101014"               # behind the cover panels, and on the spine
pages        = 24                     # only a fallback, if an interior is not built
primary_trim = "paperback"            # this trim's files are named without a suffix

[isbn]
paperback = ""
hardcover = ""

[theme]
paper       = "f4efe4"                # the page
ink         = "1a1a1a"                # body text
accent      = "7a5a1e"                # headings, rules
accent2     = "a8802e"                # ornament, frame, title
mute        = "6f6a60"                # folios, captions, incidentals
rule        = ""                      # defaults to accent
badge       = ""                      # defaults to paper
faint       = ""                      # defaults to accent2
mono_ink    = "0e2a52"                # inline code and formulas
caption_ink = ""                      # defaults to mute
backdrop    = "12100e"                # behind the page, in the reading HTML only

[epigraph]
lines       = ["One line, on the title page."]
attribution = ""

[description]
body = """
Catalogue copy. Written out as <slug>-description.txt with the title, series,
imprint, ISBN and editions above it.
"""

[fonts]                               # optional; the engine finds fonts on its own
serif = ["Regular.ttf", "Bold.ttf", "Italic.ttf", "BoldItalic.ttf"]
mono  = ["Mono.ttf", "MonoBold.ttf"]
sans  = "Sans.ttf"
```

Colours are hex, with or without a leading `#`.

### Trims

Omit `[[print.trims]]` and you get a 5×8 perfect-bound paperback and a 5.5×8.5
case-bound hardcover. Declare them to get anything else — one trim, or five:

```toml
[[print.trims]]
name = "pocket"
width = 4.25
height = 6.87
binding = "wrap"           # wrap | case
spine_per_page = 0.002347  # inches per page, from your printer's paper spec

[[print.trims]]
name = "library"
width = 6.0
height = 9.0
binding = "case"
spine_per_page = 0.002252
spine_extra = 0.06         # the boards
wrap = 0.625               # turn-in on each outer edge
hinge = 0.375              # either side of the spine
```

Every trim is typeset from the same content, so each ends up with its own page count,
and each cover is sized from **its own** interior rather than from a shared number.

---

## Templates

### `prose`

Continuous prose. Title page, flowing body, colophon.

```markdown
# A Heading
## A Subheading
Ordinary text. Consecutive lines join into one paragraph;
a blank line starts the next.

> A pull quote, set centred and apart.

---

![](art/plate.svg)                 a full-page plate
![A caption](art/figure.svg)       an inline figure at column width
![A caption](art/figure.svg){full} a full-page plate that also has a caption
// a comment, ignored
```

Body paragraphs run across a page boundary rather than jumping whole, so page bottoms
stay even. A heading never strands at the foot of a page: the room its following block
needs is reserved past it, and it moves to the next page if that will not fit.
Pull-quotes never split.

### `verse`

Sections of short numbered entries — proverbs, aphorisms, rules, clauses. Numbers hang
in their own gutter and are generated at layout time, so entries can be added or
reordered without renumbering anything.

```markdown
# First Section
One entry to a line.
The next entry.

# Second Section
Numbering restarts here.
```

### `atlas`

One numbered entry per page, each with a computed figure, grouped into parts. Fuller
front matter: half-title, title, copyright, epigraph, contents, any number of
introductory sections, then part dividers and entry pages.

```toml
[book]
template = "atlas"
figures  = "figures.py"

[copyright]
lines = ["A SHORT MANUAL", "First edition", "", "All rights reserved"]

[[front]]
kicker = "Before we begin"
title  = "Preface"
body   = """
Paragraphs, separated by blank lines.
"""

[[part]]
n = 1
label = "Foundations"
blurb = ["One line under the part title.", "And another."]

[[entry]]
n = 1
part = 1
title = "The First Idea"
figure = "first-idea"
caption = "What the figure shows."
blocks = [
  { p = "A paragraph of body text." },
  { f = "a = b + c" },              # set as a centred formula
]
```

---

## Figures

Graphs and charts are declared in the config and drawn by the engine, in the book's own
colours. No plotting library, and no code.

```toml
[[figure]]
name   = "limit"
x      = [-1, 3]
xlabel = "x"
ylabel = "y"

[[figure.curve]]
of    = "(x^2 - 1)/(x - 1)"
holes = [1]                   # break the line here, and mark the value it approaches

[[figure.point]]
at    = [1, 2]
style = "open"
label = "L = 2"
```

Use it from an atlas entry as `figure = "limit"`, or from prose or verse content as an
image whose source is the figure's name:

```markdown
![What the figure shows.](plot:limit)
```

In print it is rasterised like any other figure; in the reading HTML it is embedded as
inline SVG, so the file stays self-contained.

### Figure options

```toml
[[figure]]
name   = "..."      # required, and unique within the book
kind   = "plot"     # plot (curves from expressions) | chart (data series)
aspect = 1.6        # width / height
x      = [-5, 5]    # range; or a list of category names for a chart
y      = [0, 10]    # range; worked out from the data if omitted
xlabel = ""
ylabel = ""
title  = ""
grid   = true
axes   = true       # axes through zero; false draws a box instead
xticks = 6          # roughly how many ticks to aim for
yticks = 5
```

### Layers for `kind = "plot"`

Any number of each, drawn in this order — shading, then curves, then marks.

```toml
[[figure.curve]]                  # a function
of    = "sin(x)"
label = "sin x"                   # adds a legend entry
holes = [1]                       # removable discontinuities
dash  = false
color = "accent"                  # a theme name or a hex value
width = 2.0

[[figure.area]]                   # shading between a curve and something
of      = "x^2"
from    = 0.5
to      = 2
under   = "0"                     # the other boundary; the x axis by default
opacity = 0.16
label   = "∫"

[[figure.point]]                  # a marked point
at    = [1, 2]
style = "filled"                  # filled | open
label = ""

[[figure.line]]                   # a reference line
y     = 2                         # horizontal; use x = 1 for vertical
dash  = true
label = ""

[[figure.tangent]]                # the tangent to a curve at a point
of    = "x^2"
at    = 1.5
reach = 0.22                      # how far it extends, as a share of the x range
label = ""

[[figure.note]]                   # free text at a data coordinate
at   = [1.4, 3.4]
text = "approaches 2"
```

### Layers for `kind = "chart"`

```toml
[[figure.series]]
type   = "bar"                    # bar | line | scatter | step
values = [31, 36, 29, 38, 33, 33]
at     = []                       # x positions; indices or categories by default
label  = ""
color  = "accent"
points = false                    # line only: mark each value
dash   = false
```

### Expressions

`+ - * / % //`, `^` for powers, brackets, and comparisons. Piecewise definitions work
through a conditional: `"x if x > 0 else -x"`. Available functions are `sin cos tan asin
acos atan atan2 sinh cosh tanh exp log ln log10 log2 sqrt hypot abs floor ceil round min
max pow copysign degrees radians erf gamma factorial`, and the constants `pi e tau inf`.

Expressions are parsed and walked under a whitelist rather than evaluated, so a config
file cannot reach outside that list.

### Computed figures

For artwork that genuinely has to be generated rather than declared, a book can name a
Python module instead:

```toml
[book]
figures = "figures.py"          # a file beside the config, or an importable module
```

supplying:

```python
def figure_svg(name: str) -> str:
    """Return the named figure as a complete SVG document."""

def aspect(name: str) -> float:
    """Return its width divided by its height."""
```

A book may use both. A declared figure wins if the two define the same name.

---

## Cover art

Supply `art/front-cover.svg` and `art/back-cover.svg`. Without both, covers are skipped
and the interiors still build.

A cover wrap is one flat sheet: back panel, spine, front panel, sized around the
finished book. For a `wrap` binding the panels are stretched to the exact bleed size.
For a `case` binding they are placed across each board's trim area at their own
proportions and allowed to bleed past the top and bottom, so the same art serves both.

Panels are rasterised at 300 dpi.

---

## Output

For a book with slug `short-manual` and the default trims:

```
dist/
  short-manual-interior.pdf                 5 x 8, with bleed
  short-manual-interior-hardcover.pdf       5.5 x 8.5, with bleed
  short-manual-cover-wrap.pdf               back + spine + front
  short-manual-cover-wrap-hardcover.pdf     case wrap with hinges and turn-in
  short-manual-interior.html                self-contained reading copy
  short-manual-description.txt              catalogue listing
```

The primary trim's files carry no suffix, so adding a trim later does not rename the
files you already have.

Every PDF has all fonts embedded. reportlab writes an unused font tag into each page
and references it from the content stream; deleting the resource would leave a dangling
reference that some print processors reject, so instead every unembedded entry is
pointed at a font that is genuinely embedded.

---

## Python API

```python
from publishing_engine import build, load, discover

result = build("books/short-manual")
result.pages         # {"paperback": 34, "hardcover": 28}
result.pdfs          # every PDF written
result.html          # the reading copy
result.description   # the listing

book = load("books/short-manual")   # inspect without building
book.primary().spine(34)            # spine thickness in inches

for directory in discover("books"):
    build(directory)
```

`build()` takes `covers=False` and `html=False` to skip either.

---

## Command line

```
publish build [book ...]   build one, several, or everything found
                           --root DIR   where to look (default: .)
                           --no-covers  skip cover wraps
                           --no-html    skip the reading copy
publish list               list the books found
publish new DIR            start a book from the worked example
publish templates          list the available templates
```

---

## Older key names

An earlier config shape is accepted, so a project written against it keeps building
without being rewritten. Each of these maps onto its canonical equivalent:

| accepted | canonical |
|---|---|
| `manifesto.toml` | `book.toml` |
| `[meta]` | `[book]` |
| `[meta].manifesto` | `[book].title` |
| `[meta].series_label`, `[meta].volume` | `[series].label`, `[series].volume` |
| `[meta].content_file`, `[meta].proverbs_file` | `[book].content` |
| `[meta.print]`, `[meta.isbn]` | `[print]`, `[isbn]` |
| `[skin]` | `[theme]` |
| `[skin].bronze`, `[skin].bronze2` | `[theme].accent`, `[theme].accent2` |
| `[[axiom]]` | `[[entry]]` |
| `[preface]`, `[notation]` | `[[front]]` |
| entry key `graph` | entry key `figure` |
| template `bible` / `axiom` / `plate` | `verse` / `atlas` / `prose` |

New books should use the canonical names; the old ones are resolved in
`config.py` and are not used anywhere else in the engine.

---

## Printing notes

The defaults suit common print-on-demand requirements, but check them against your
printer's own spec:

* **Bleed** 0.125″ on every edge; the interior page is `trim + 0.125″ × trim + 0.25″`.
* **Margins** the text column sits about 0.61″ inside the trim, clear of the usual
  0.375″ gutter and outside minimums.
* **Images** cover panels at 300 dpi, plates at ~312 dpi on a 5×8 page.
* **Page count** padded to `min_pages` and to an even number. Colour printing often has
  a higher minimum than mono; 24 is the usual floor for premium colour, 72 for standard.
* **Spine text** most printers require ~79 pages before they will print on a spine.
  Nothing is set on the spine here.

Useful checks on the output, if you have poppler or qpdf to hand:

```bash
pdffonts file.pdf      # every row should read emb=yes
pdfimages -list file.pdf
qpdf --check file.pdf
pdfinfo file.pdf       # page size and count
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

The suite covers config loading, the content parsers, the markup, the colour helpers,
and an end-to-end build of the example book — checking page counts, page geometry,
cover width against the computed spine, and that every font in every output is embedded.

[`CONTEXT.md`](CONTEXT.md) has the architecture, the contracts a template and a figure
module must honour, the page geometry every template shares, and the rendering gotchas
worth knowing before you spend an afternoon on one.
