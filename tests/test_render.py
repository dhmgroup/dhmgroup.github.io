from app.legal.render import render_markdown


def test_basic_markdown():
    html = render_markdown("## Heading\n\nSome **bold** text and a [link](https://dhmgroup.net).")
    assert "<h2>Heading</h2>" in html
    assert "<strong>bold</strong>" in html
    assert 'href="https://dhmgroup.net"' in html


def test_raw_html_is_not_rendered():
    html = render_markdown(
        '<script>alert(1)</script>\n\n<iframe src="https://evil.test"></iframe>\n\n'
        '<img src=x onerror="alert(1)">'
    )
    assert "<script" not in html
    assert "<iframe" not in html
    assert "<img" not in html


def test_javascript_links_are_neutralised():
    html = render_markdown("[click](javascript:alert(1))")
    assert 'href="javascript' not in html
