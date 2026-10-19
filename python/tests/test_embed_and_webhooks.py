import base64
import json
from urllib.parse import unquote

from euromar_signing import build_embed_url, parse_event, verify_secret


def _decode_hash(url: str) -> dict:
    return json.loads(unquote(base64.b64decode(url.split("#", 1)[1]).decode()))


def test_embed_url_shape_and_options():
    url = build_embed_url(
        "https://sign.example.com/", "tok_123", name="Jane Signer", email="jane@x.test"
    )
    assert url.startswith("https://sign.example.com/embed/sign/tok_123#")
    opts = _decode_hash(url)
    assert opts == {
        "darkModeDisabled": True,
        "allowDocumentRejection": False,
        "name": "Jane Signer",
        "lockName": True,
        "email": "jane@x.test",
        "lockEmail": True,
    }


def test_embed_url_handles_non_ascii_names():
    opts = _decode_hash(build_embed_url("https://s", "t", name="João Câmara"))
    assert opts["name"] == "João Câmara"


def test_verify_secret():
    assert verify_secret("s3cret", "s3cret")
    assert not verify_secret("nope", "s3cret")
    assert not verify_secret(None, "s3cret")
    assert not verify_secret("s3cret", "")


def test_parse_event():
    body = json.dumps(
        {
            "event": "DOCUMENT_COMPLETED",
            "payload": {"envelopeId": "envelope_x", "externalId": "app:1", "status": "COMPLETED"},
            "createdAt": "2026-10-19T10:00:00Z",
            "webhookEndpoint": "https://app/webhook",
        }
    )
    ev = parse_event(body)
    assert ev.event == "DOCUMENT_COMPLETED"
    assert ev.envelope_id == "envelope_x"
    assert ev.external_id == "app:1"
    assert ev.status == "COMPLETED"
