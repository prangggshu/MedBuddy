"""Safe upload validation and PDF-to-image adaptation for prescription intake."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile


ALLOWED = {
    "image/jpeg": (".jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (".webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    "application/pdf": (".pdf", lambda b: b.startswith(b"%PDF-")),
}


def safe_display_name(name: str | None) -> str:
    clean = (name or "prescription").replace("\\", "/").split("/")[-1]
    clean = "".join(c for c in clean if c.isalnum() or c in " ._-()").strip(" .")
    return clean[:200] or "prescription"


async def read_upload(
    upload: UploadFile, max_bytes: int, destination_dir: Path
) -> tuple[bytes, str, str, Path]:
    data = bytearray()
    destination_dir.mkdir(parents=True, exist_ok=True)
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination_dir, prefix=".upload-", delete=False) as out:
            path = Path(out.name)
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise HTTPException(413, detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                out.write(chunk)
        raw = bytes(data)
        for mime, (extension, validator) in ALLOWED.items():
            if validator(raw):
                return raw, mime, extension, path
        raise HTTPException(415, detail="Unsupported file. Upload a JPEG, PNG, WebP, or PDF.")
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise


def pdf_first_pages(data: bytes, max_pages: int = 3) -> tuple[list[bytes], int, str]:
    """Render up to three PDF pages as PNG images. Returns pages, total, MIME."""
    import fitz

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.page_count < 1:
            raise ValueError("PDF has no pages")
        pages = [doc.load_page(i).get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                 for i in range(min(doc.page_count, max_pages))]
        return pages, doc.page_count, "image/png"
    except Exception as exc:
        raise HTTPException(422, detail="Could not read this PDF.") from exc
