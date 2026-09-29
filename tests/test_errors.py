async def test_unknown_path_renders_designed_404(client):
    r = await client.get("/no-such-page")
    assert r.status_code == 404
    assert "This page does not exist." in r.text
    assert "/static/dist/app.css" in r.text


async def test_static_css_entry_is_served(client):
    r = await client.get("/static/src/app.css")
    assert r.status_code == 200
