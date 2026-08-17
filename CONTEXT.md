# Engine specs — to be followed for every change

Conventions and invariants for working on `publishing-engine`. The [README](README.md)
is for people using the engine; this is for people changing it.

---

## The boundary

**The engine knows nothing about any particular book.** No title, series name, imprint,
colour, trim, figure or turn of phrase belonging to a real book may enter this
repository. Everything a book needs to describe itself goes in the book's own directory,
in its config. Books live in their own repository.

Two checks before any change lands:

```bash
grep -rn -i "<a real book's title or series>" --include="*.py" .   # must find nothing
pytest                                                             # must pass
```

The one deliberate exception is the compatibility layer in `config.py`, which maps an
older set of key names onto the canonical ones. Those names are generic
(`manifesto`, `skin`, `axiom`) and are resolved in that module alone. **Do not let them
spread**: no other module may read a legacy key.

The `examples/sample-book` book exists so the engine has something to build in tests and
in `publish new`. It is deliberately dull and generic; keep it that way.

---

## Architecture

Data flows one way. Config is normalised once, then everything downstream reads a
`Book`.

```
config.load(dir) ─► Book ─┬─► templates.<name>.build_pdf  ─► interior PDFs + page counts
                          ├─► templates.<name>.build_html ─► reading HTML
                          ├─► cover.build                 ─► cover wraps (needs page counts)
                          └─► builder.write_listing       ─► catalogue text
                                        │
                                        └─► pdftools.embed_fonts on every PDF
```

| Module | Responsibility |
|---|---|
| `config.py` | Load and normalise a book config. The **only** place that knows legacy key names, defaults, or how a `Trim` and `Theme` are assembled. |
| `builder.py` | Orchestrate one book's build; own `dist/` and the scratch directory. |
| `page.py` | `Sheet` — page geometry, the cursor, drawing primitives, shared front and back matter. Frames live here too. |
| `templates/` | One module per template, each a `build_pdf` and a `build_html` over the same content. |
| `sources/` | Content parsers. Pure functions: file in, list of blocks out. No layout, no reportlab. |
| `markup.py` | Inline markup to reportlab, to HTML, or to bare text. |
| `cover.py` | Cover wrap geometry and assembly, per binding. |
| `fonts.py` | Font registration, metrics, and the wrapping and fitting helpers. |
| `raster.py` | SVG to PNG. The only module that calls cairosvg. |
| `pdftools.py` | Font-embedding hygiene on finished PDFs. The only module that calls pikepdf. |
| `figures.py` | Resolve a figure by name: a declaration first, a book's own module second. |
| `plotting/` | Draw a declared figure. `expr` evaluates expressions under a whitelist, `scale` maps data to the page and picks ticks, `svg` writes the document, `draw` assembles it. |
| `palette.py`, `numbers.py` | Small pure helpers — colour arithmetic, numbers as words and numerals. |
| `cli.py` | Argument parsing only. No logic that is not also reachable from the API. |

**Keep third-party libraries behind their module.** cairosvg belongs to `raster.py`,
pikepdf to `pdftools.py`. If a template needs a raster, it calls `raster`.

---

## Contracts

Breaking one of these breaks every book. Change them deliberately, and update
`templates/__init__.py` and the tests in the same commit.

**Template**

```python
build_pdf(book, dist_dir, render_dir) -> (list[str], dict[str, int])
build_html(book, dist_dir)            -> str
```

The dict maps trim name to the real page count of that trim. `cover.py` sizes each spine
from it, so it must be the count *after* padding. A template that does not build a PDF
per trim will produce covers sized from the fallback in `[print].pages`.

**Figure module** (supplied by the book, not by the engine)

```python
figure_svg(name) -> str     # a complete SVG document
aspect(name)     -> float   # width / height
```

**Figure source** — `figures.for_book(book)` answers `svg(name)` and `aspect(name)`
from whichever source defines the name, declaration first. Templates go through it and
never load a module themselves.

**Frame** — anything with an `inner_inset` attribute and a `__call__(sheet, folio)`.
`inner_inset` is what `Sheet.safe_width()` measures from, so a frame that draws a rule at
a different inset must declare it, or centred front matter will run into the frame.

**Result** — `builder.Result`. Add fields; do not repurpose existing ones.

---

## Page geometry

Canonical, and shared by every template.

**Coordinates.** A page is opened with the origin already translated to the bottom-left
of the **trim**, so templates work in trim coordinates (`0..sheet.tw`, `0..sheet.th`) and
never do bleed arithmetic. The canvas itself is larger:

```
page width  = trim width  + bleed          (bleed on the outer edge only)
page height = trim height + 2 × bleed
```

Odd pages (rectos) bleed right, even pages (versos) bleed left. `Sheet._offsets()`
alternates this. **Never draw outside the trim box** — it will be cut off on one side and
not the other.

**Defaults** — `Sheet(margin=54, top=76, bottom=60)`, i.e. the text column is
`tw - 108` wide, running from `th - 76` down to `60`. The `atlas` template overrides
`margin=46` to match its narrower frame.

**Frames** — `DoubleRule` (inner inset 28) for `prose` and `verse`; `CornerMarks`
(inner inset 23) for `atlas`; `Plain` (0) for anything unframed.

**Figure caps** — a figure is scaled to the column width, then capped by height:
`0.52 × page height` in `prose`, `0.40 × page height` in `atlas`. A figure taller than
its cap is scaled down *by height*, so it ends up **narrower than the column**. This is
the usual cause of a figure looking unexpectedly small: keep art at or under a
600 × 714 aspect for `prose` if you want full column width.

**Padding** — every interior is padded with framed blank pages to `[print].min_pages`
and to an even count. Both conditions, always: a book block is printed on folded sheets
and an odd count is not a thing that exists.

---

## Typography

Fonts are registered under stable internal names — `BookSerif` (`-B`, `-I`, `-BI`),
`BookMono` (`-B`), `BookSans` — and everything refers to those, never to a file or to a
built-in name.

**reportlab's built-in Times and Helvetica are not embedded in the output.** Most print
services reject that, so real TrueType files are always registered and used. Never call
`setFont("Helvetica", …)`.

**Every finished PDF passes through `pdftools.embed_fonts`.** reportlab writes an unused
font tag into each page's resources *and* references it from the content stream:
deleting the resource leaves a dangling reference, which is worse than the phantom. So
each unembedded entry is aliased to a font that is genuinely embedded. A cover wrap sets
no type of its own and so has no embedded font to alias to — for those a minimal donor
document is generated and its font copied in. There is a test asserting every font in
every output is embedded; keep it passing.

**Markup** is neutral about its destination, since the same text is set into PDF and
HTML. Two glyphs are swapped on the PDF side only, because Times and Liberation have no
drawing for them: `∬`/`∭` expand to repeated single integrals, and `⇒` — which those
faces carry as a blank — becomes `→`. HTML keeps the originals. Add to
`markup.PDF_SUBSTITUTIONS` if another blank glyph turns up.

---

## Covers

A cover is one flat sheet: back panel, spine, front panel.

```
wrap   width  = 2 × trim width + spine + 2 × bleed
       height = trim height + 2 × bleed
       spine  = pages × spine_per_page

case   width  = 2 × (wrap + bleed) + 2 × trim width + 2 × hinge + spine
       height = 2 × (wrap + bleed) + trim height
       spine  = pages × spine_per_page + spine_extra
```

Panels are rasterised at **300 dpi**. For a `wrap` the panel is forced to the exact bleed
size, so art must be drawn at that proportion. For a `case` the panel is rendered at
board width **keeping its own aspect** and allowed to bleed past the top and bottom board
edges — which is what lets one piece of art serve both bindings. Do not reintroduce a
hardcoded panel pixel height; the aspect is read from the rendered art.

**Each spine is sized from its own trim's page count.** The two trims hold different
amounts of text and genuinely differ — a book can run 46 pages as a paperback and 38 as a
hardcover.

---

## Output naming

`<slug>-<kind>.<ext>` for the primary trim, `<slug>-<kind>-<trim>.<ext>` for every other.
This keeps existing filenames stable when a trim is added later. It is implemented once,
in `Book.output_name`; do not build filenames anywhere else.

---

## Known rendering gotchas

**cairosvg mis-spaces italic `f`.** Its toy font inserts a spurious space after every
`f` in italic text: `confidant flow off` renders as `conf idant f low of f`. Regular
weight is unaffected, as are reportlab interiors and HTML — this is SVG art only. Either
keep italic SVG text free of the letter `f`, or set it in regular weight with a
`skewX(-12)` transform to keep the slant.

**Never set SVG text in a real italic.** The same rasteriser bug is why
`plotting.svg.text` takes `slant=True` — a `skewX` transform — rather than
`font-style="italic"`. Mathematical labels are mostly `f`s; a real italic wrecks them.
There is a test asserting no figure emits `font-style`.

**SVG text does not wrap.** Nothing in an SVG figure reflows, so a long string will run
past the artwork margin or under a panel. Figures are also scaled down when placed, so
9-unit text on a 600-unit canvas lands at roughly 4pt in print. Check the rendered page,
not the SVG.

**A raster is not a proof.** A build that succeeds tells you nothing about layout.
Rasterise and look — collisions, overflow and figures that read as blobs all pass the
build in silence.

---

## Parity

The engine was extracted from an earlier per-book toolchain and reproduces its output
**pixel-identically** for the `prose` and `verse` templates, including cover wrap
geometry. Two deviations are deliberate:

- `atlas` caption colour now comes from `theme.caption_ink` (defaulting to `mute`)
  instead of a hardcoded slate.
- Cover wraps now have their fonts embedded; previously they did not.

If a change alters rendered output, say so explicitly and show what moved. Rendering
changes are not refactors.

---

## Testing

```bash
pip install -e ".[dev]"
pytest
```

- `test_config.py` — loading, defaults, aliases, trims, theme derivation, discovery.
- `test_content.py` — the parsers, the markup, numbers, colour. Pure and fast.
- `test_plotting.py` — expressions (including a battery of unsafe ones that must be
  refused), tick selection, and that each layer and series type draws something.
- `test_figures.py` — which source a figure name resolves to.
- `test_build.py` — an end-to-end build of the example: page counts, page geometry,
  cover width against the computed spine, HTML contents, and font embedding.

Add a config or parser test for every new key or block type. Add an assertion to
`test_build.py` for anything that must be true of the finished artefact.

---

## Declared figures

A book should not need a programmer to get a graph. Anything a maths or science volume
commonly needs belongs in `plotting/` as a declarative option, not in a book's own
Python. The module escape hatch stays for genuinely bespoke artwork, but reach for it
last — if a book has to write code to draw something ordinary, that is a gap in
`plotting/`.

Two rules for that package:

- **Expressions are never evaluated, only walked.** `expr.py` whitelists node types,
  names and functions. Widening it is a security decision, not a convenience one.
- **Everything is themed.** A figure takes its colours from the book's `[theme]`, so it
  sits in the book rather than on it. No literal colour belongs in `draw.py` outside the
  theme lookup.

---

## Code style

- Docstrings explain **why**, not what. The reader can see what.
- Constants that encode a print requirement get a comment saying whose requirement.
- No dead code. If a feature is removed, remove it — do not leave it unreferenced.
- Prefer adding to `Sheet` over copying page furniture into a template. Duplication
  between templates is what this engine was built to remove.
