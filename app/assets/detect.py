"""File type from magic bytes. Uploaded names and client Content-Types are never trusted."""

IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/avif",
    "image/svg+xml",
    "image/x-icon",
}


def detect(head: bytes) -> tuple[str, str] | None:
    """(extension, content type) for the allowed upload types, else None. Pass >= 512 bytes."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp", "image/webp"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif", "image/avif"
    if head.startswith(b"\x00\x00\x01\x00"):
        return ".ico", "image/x-icon"
    if head.startswith(b"%PDF-"):
        return ".pdf", "application/pdf"
    text = head[:512].lstrip().lower()
    if text.startswith(b"<svg") or (text.startswith(b"<?xml") and b"<svg" in text):
        return ".svg", "image/svg+xml"
    return None
