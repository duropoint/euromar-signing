from __future__ import annotations

import pymupdf
import pytest


def make_pdf(text: str, *, pages: int = 1, caption: str = "Signature:") -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 100), f"{text} - page {i + 1}", fontsize=14)
        if i == pages - 1:
            page.insert_text((72, 640), caption, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_factory():
    return make_pdf
