import pymupdf
import pytest

from euromar_signing import TextStamp, box_near_text, find_text, stamp_text, to_signature_box


def test_find_text_last_occurrence(pdf_factory):
    pdf = pdf_factory("Form", pages=3)
    anchor = find_text(pdf, "Signature:")
    assert anchor is not None
    assert anchor.page_index == 2
    assert anchor.page_width == 595 and anchor.page_height == 842
    assert 620 < anchor.y1 < 660


def test_find_text_missing(pdf_factory):
    assert find_text(pdf_factory("Form"), "Not there") is None


def test_to_signature_box_converts_to_percent_and_one_based_page():
    box = to_signature_box(0, 59.5, 84.2, 119, 42.1, 595, 842)
    assert box.page == 1
    assert box.x == pytest.approx(10)
    assert box.y == pytest.approx(10)
    assert box.width == pytest.approx(20)
    assert box.height == pytest.approx(5)


def test_to_signature_box_clamps_onto_page():
    box = to_signature_box(0, 590, 830, 100, 50, 595, 842)
    assert box.x + box.width <= 100
    assert box.y + box.height <= 100


def test_box_near_text_sits_under_caption(pdf_factory):
    pdf = pdf_factory("Form", pages=2)
    anchor = find_text(pdf, "Signature:")
    box = box_near_text(pdf, "Signature:", dy=4, height=45)
    assert box.page == 2
    assert box.y == pytest.approx((anchor.y1 + 4) / 842 * 100, abs=0.01)


def test_box_near_text_fallback_last_page(pdf_factory):
    pdf = pdf_factory("Form", pages=2, caption="Something else")
    box = box_near_text(pdf, "Signature:")
    assert box.page == 2
    assert box.y > 80


def test_box_near_text_without_fallback_raises(pdf_factory):
    with pytest.raises(LookupError):
        box_near_text(pdf_factory("Form", caption="x"), "Signature:", fallback=None)


def test_stamp_text_adds_text(pdf_factory):
    out = stamp_text(pdf_factory("Form"), [TextStamp(0, 72, 700, "Name: Jane Signer")])
    with pymupdf.open(stream=out, filetype="pdf") as doc:
        assert "Name: Jane Signer" in doc[0].get_text()


def test_stamp_text_rejects_bad_page(pdf_factory):
    with pytest.raises(ValueError):
        stamp_text(pdf_factory("Form"), [TextStamp(3, 72, 700, "x")])
