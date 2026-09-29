from functools import lru_cache

import nh3
from markdown_it import MarkdownIt

# html=False escapes raw HTML in the source; nh3 is the second line of defence.
_md = MarkdownIt("commonmark", {"html": False}).enable("table")

# Spec allowlist: headings, paragraphs, lists, links, emphasis, code, blockquote, tables. No images.
ALLOWED_TAGS = {
    *("h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr"),
    *("ul", "ol", "li", "a", "em", "strong", "code", "pre", "blockquote"),
    *("table", "thead", "tbody", "tr", "th", "td"),
}


@lru_cache(maxsize=64)
def render_markdown(source: str) -> str:
    return nh3.clean(_md.render(source), tags=ALLOWED_TAGS)
