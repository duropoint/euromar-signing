"""PDF helpers: find where a signature belongs, and stamp prefilled text.

All coordinates in PDF points with a top-left origin (PyMuPDF's convention)
unless stated otherwise. `to_signature_box` converts to Documenso's units.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

from .models import SignatureBox


@dataclass(frozen=True)
class Anchor:
    """A text match on a page: 0-based page index, match rect and page size."""

    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float


@dataclass(frozen=True)
class TextStamp:
    """Text to draw at (x, y) = baseline start, 0-based page index."""

    page_index: int
    x: float
    y: float
    text: str
    fontsize: float = 10.0


def page_count(pdf: bytes) -> int:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return doc.page_count


def find_text(pdf: bytes, text: str, *, occurrence: str = "last") -> Anchor | None:
    """Locate `text` in the PDF. `occurrence` is "first" or "last" (signature
    lines usually sit on the last match, e.g. after repeated headings)."""
    if occurrence not in ("first", "last"):
        raise ValueError("occurrence must be 'first' or 'last'")
    found: Anchor | None = None
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = range(doc.page_count)
        if occurrence == "last":
            pages = reversed(pages)
        for index in pages:
            page = doc[index]
            hits = page.search_for(text)
            if not hits:
                continue
            rect = hits[-1] if occurrence == "last" else hits[0]
            found = Anchor(
                index, rect.x0, rect.y0, rect.x1, rect.y1, page.rect.width, page.rect.height
            )
            break
    return found


def to_signature_box(
    page_index: int, x: float, y: float, width: float, height: float, page_w: float, page_h: float
) -> SignatureBox:
    """Points (top-left origin, 0-based page) -> Documenso box (1-based page,
    percentages), clamped onto the page."""
    width = min(width, page_w)
    height = min(height, page_h)
    x = max(0.0, min(x, page_w - width))
    y = max(0.0, min(y, page_h - height))
    return SignatureBox(
        page=page_index + 1,
        x=round(x / page_w * 100, 4),
        y=round(y / page_h * 100, 4),
        width=round(width / page_w * 100, 4),
        height=round(height / page_h * 100, 4),
    )


def box_near_text(
    pdf: bytes,
    text: str,
    *,
    dx: float = 0.0,
    dy: float = 4.0,
    width: float = 180.0,
    height: float = 45.0,
    occurrence: str = "last",
    fallback: str = "last-page-bottom",
) -> SignatureBox:
    """Signature box positioned relative to a caption found in the PDF.

    The box's top-left is (anchor.x0 + dx, anchor.y1 + dy), i.e. by default
    just under the caption. If the caption is not found and `fallback` is
    "last-page-bottom", the box goes at the bottom-left of the last page;
    with fallback=None a LookupError is raised.
    """
    anchor = find_text(pdf, text, occurrence=occurrence)
    if anchor is not None:
        return to_signature_box(
            anchor.page_index,
            anchor.x0 + dx,
            anchor.y1 + dy,
            width,
            height,
            anchor.page_width,
            anchor.page_height,
        )
    if fallback != "last-page-bottom":
        raise LookupError(f"signature caption {text!r} not found")
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        last = doc[doc.page_count - 1]
        w, h = last.rect.width, last.rect.height
        return to_signature_box(doc.page_count - 1, 56, h - height - 56, width, height, w, h)


def stamp_text(pdf: bytes, stamps: list[TextStamp]) -> bytes:
    """Draw plain text onto the PDF before it is sent for signing; the
    Documenso seal then covers it like the rest of the page."""
    if not stamps:
        return pdf
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for s in stamps:
            if not 0 <= s.page_index < doc.page_count:
                raise ValueError(f"page {s.page_index} out of range")
            doc[s.page_index].insert_text(
                (s.x, s.y), s.text, fontsize=s.fontsize, fontname="helv", color=(0, 0, 0)
            )
        return doc.tobytes(garbage=3, deflate=True)
