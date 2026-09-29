from functools import lru_cache

import nh3
from markdown_it import MarkdownIt

# html=False escapes raw HTML in the source; nh3 is the second line of defence.
_md = MarkdownIt("commonmark", {"html": False}).enable("table")


@lru_cache(maxsize=64)
def render_markdown(source: str) -> str:
    return nh3.clean(_md.render(source))
