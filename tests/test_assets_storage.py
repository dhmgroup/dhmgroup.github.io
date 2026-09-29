import uuid

import pytest

from app.assets import storage
from app.assets.detect import detect

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (PNG, (".png", "image/png")),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 16, (".jpg", "image/jpeg")),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", (".webp", "image/webp")),
        (b"\x00\x00\x00\x1cftypavif", (".avif", "image/avif")),
        (
            b"  <?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'/>",
            (".svg", "image/svg+xml"),
        ),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", (".svg", "image/svg+xml")),
        (b"\x00\x00\x01\x00\x01\x00", (".ico", "image/x-icon")),
        (b"%PDF-1.7\n", (".pdf", "application/pdf")),
    ],
)
def test_detect_known_types(head, expected):
    assert detect(head) == expected


@pytest.mark.parametrize(
    "head",
    [b"<!doctype html><html>", b"MZ\x90\x00", b"GIF89a", b"", b"<?xml version='1.0'?><note/>"],
)
def test_detect_rejects_everything_else(head):
    assert detect(head) is None


async def test_put_public_url_and_delete():
    key = f"uploads/test-{uuid.uuid4()}.png"
    await storage.put(key, PNG, "image/png")
    assert await storage.exists(key)
    assert storage.public_url(key) == f"http://localhost:9000/dhm-test/{key}"
    await storage.delete(key)
    assert not await storage.exists(key)
