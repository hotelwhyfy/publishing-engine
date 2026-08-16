"""The shared shell for every reading-HTML template.

One page, centred on a backdrop, set in the book's own colours: the front matter, then
whatever the template renders, then the closing line. Each template adds only the CSS
for the blocks it actually produces.
"""
from __future__ import annotations

from .. import palette
from ..markup import to_html

RULE = ('<div class="rule"><span class="l"></span><span class="d"></span>'
        '<span class="l"></span></div>')


def base_css(theme):
    hairline = palette.rgba(theme.accent2, 0.5)
    return f"""
  :root {{
    --paper:#{theme.paper}; --ink:#{theme.ink};
    --accent:#{theme.accent}; --accent2:#{theme.accent2};
    --mute:#{theme.mute}; --mono-ink:#{theme.mono_ink};
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:48px 16px; background:{palette.backdrop(theme.backdrop)} fixed;
    color:var(--ink); font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    line-height:1.7; font-size:18px; }}
  .page {{ max-width:760px; margin:0 auto; background:var(--paper); padding:64px 60px 80px;
    box-shadow:0 24px 60px rgba(0,0,0,.6); border:1.5px solid var(--accent2); position:relative; }}
  .page::before {{ content:""; position:absolute; inset:10px; border:.8px solid {hairline};
    pointer-events:none; }}
  .eyebrow {{ text-align:center; letter-spacing:.3em; text-transform:uppercase;
    font-size:.7rem; color:var(--mute); margin:0 0 12px; }}
  .title {{ text-align:center; font-size:clamp(2.2rem,8vw,3.2rem); line-height:1.05;
    letter-spacing:.06em; margin:0; font-weight:700; color:var(--accent2); }}
  .rule {{ display:flex; align-items:center; justify-content:center; gap:12px; margin:24px auto; }}
  .rule .l {{ height:1px; width:60px; background:{palette.rgba(theme.accent2, 0.6)}; }}
  .rule .d {{ width:7px; height:7px; background:var(--accent2); transform:rotate(45deg); }}
  .subtitle {{ text-align:center; font-style:italic; font-size:1.12rem; margin:.4em 0 0; }}
  .epigraph {{ text-align:center; font-style:italic; color:var(--mute); font-size:.98rem;
    margin:1em auto 0; max-width:40ch; }}
  .imprint {{ text-align:center; letter-spacing:.28em; text-transform:uppercase;
    font-size:.68rem; color:var(--mute); margin:2.2em 0 0; }}
  .end {{ text-align:center; font-style:italic; font-size:1.1rem; margin:48px 0 0; }}
  code {{ font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; font-size:.92em;
    color:var(--mono-ink); }}
  @media (max-width:560px) {{
    body {{ padding:18px 8px; }} .page {{ padding:40px 24px 56px; }}
  }}
"""


def document(book, body, extra_css="", head_title=None):
    """Wrap a rendered *body* in the full page, with front matter and closing line."""
    theme = book.theme
    epigraph = (book.epigraph.get("lines") or [""])[0]
    eyebrow = f'<p class="eyebrow">{book.series_label}</p>' if book.series_label else ""
    subtitle = f'<p class="subtitle">{book.subtitle}</p>' if book.subtitle else ""
    epi = f'<p class="epigraph">{to_html(epigraph)}</p>' if epigraph else ""
    imprint = f'<p class="imprint">{book.imprint}</p>' if book.imprint else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_title or book.title}</title>
<style>{base_css(theme)}{extra_css}</style></head>
<body><main class="page">
  {eyebrow}
  <h1 class="title">{' '.join(book.title_lines)}</h1>
  {RULE}
  {subtitle}
  {epi}
  {imprint}

  {body}

  {RULE}
  <p class="end">{book.closing_line()}</p>
  {imprint}
</main></body></html>
"""
