from app.seed import seed


async def test_app_ads_txt(client):
    r = await client.get("/app-ads.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "google.com, pub-7456853939285004, DIRECT, f08c47fec0942fa0" in r.text


async def test_robots(client):
    r = await client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /admin" in r.text
    assert "Sitemap: http://localhost:8000/sitemap.xml" in r.text


async def test_sitemap_lists_home_and_published_legal(client, session):
    await seed(session)
    r = await client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert "<loc>http://localhost:8000/</loc>" in r.text
    assert "<loc>http://localhost:8000/legal/privacy</loc>" in r.text
    assert "<loc>http://localhost:8000/legal/terms</loc>" in r.text
