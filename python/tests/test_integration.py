"""End-to-end against a real Documenso (the pinned image).

    deploy/scripts/bootstrap-local.sh
    pytest -m integration

Covers what an app relies on: session creation over several PDFs without
any email, signing through the embed (one signature reused across
documents), the completion postMessage, the webhook, the sealed PAdES PDFs
+ evidence, cancellation, and the purge job.
"""

from __future__ import annotations

import http.server
import io
import json
import os
import socketserver
import threading
import time
from pathlib import Path

import httpx
import psycopg
import pymupdf
import pytest

from euromar_signing import (
    SECRET_HEADER,
    DocumensoNotFound,
    Signer,
    SigningDocument,
    SigningService,
    TextStamp,
    box_near_text,
    parse_event,
    stamp_text,
    verify_secret,
)
from euromar_signing.purge import purge

from .signing_bot import sign_in_embed

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / "deploy" / ".local" / "env"
WEBHOOK_PORT = 8765


def _load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    env.update({k: v for k, v in os.environ.items() if k.startswith("DOCUMENSO_")})
    return env


@pytest.fixture(scope="module")
def env():
    env = _load_env()
    if "DOCUMENSO_API_TOKEN" not in env:
        pytest.skip("run deploy/scripts/bootstrap-local.sh first")
    return env


@pytest.fixture(scope="module")
def service(env):
    svc = SigningService.from_settings(env["DOCUMENSO_URL"], env["DOCUMENSO_API_TOKEN"])
    yield svc
    svc.client.close()


@pytest.fixture(scope="module")
def webhooks():
    received: list[dict] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append({"headers": dict(self.headers), "body": body})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", WEBHOOK_PORT), Handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield received
        httpd.shutdown()


def _form(title: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), title, fontsize=16)
    page.insert_text((72, 600), "Signature of the declarant:", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _document(name: str, title: str) -> SigningDocument:
    pdf = stamp_text(
        _form(title),
        [
            TextStamp(0, 72, 700, "Name: Jane Signer"),
            TextStamp(0, 72, 716, "Place: Funchal"),
        ],
    )
    return SigningDocument(name, pdf, [box_near_text(pdf, "Signature of the declarant:")])


def _wait_for(predicate, timeout=45, interval=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def test_full_signing_flow(env, service, webhooks):
    docs = [_document("Part 1.pdf", "CPP PART 1"), _document("Appendix.pdf", "ISM APPENDIX")]
    signer = Signer("Jane Signer", "jane.signer@example.test")
    session = service.start(
        title="Integration test", signer=signer, documents=docs, external_id="it:1"
    )
    assert set(session.items) == {"Part 1.pdf", "Appendix.pdf"}
    assert "/embed/sign/" in session.embed_url

    # Nothing was mailed to the signer.
    mails = httpx.get("http://localhost:8025/api/v1/messages").json().get("messages", [])
    assert not any(any(t["Address"] == signer.email for t in m.get("To", [])) for m in mails)

    pending = service.fetch_result(session.envelope_id)
    assert pending.status == "PENDING" and pending.documents == {}

    messages = sign_in_embed(session.embed_url, typed_signature="Jane Signer")
    origin = env["DOCUMENSO_URL"]
    completed = [m for m in messages if m["data"].get("action") == "document-completed"]
    assert completed and completed[0]["origin"] == origin
    assert completed[0]["data"]["data"]["envelopeId"] == session.envelope_id

    # Webhook: authenticated by the shared secret, points at our envelope.
    hook = _wait_for(
        lambda: next(
            (
                w
                for w in webhooks
                if parse_event(w["body"]).envelope_id == session.envelope_id
                and parse_event(w["body"]).event == "DOCUMENT_COMPLETED"
            ),
            None,
        )
    )
    assert hook, "no DOCUMENT_COMPLETED webhook received"
    headers = {k.lower(): v for k, v in hook["headers"].items()}
    assert verify_secret(headers.get(SECRET_HEADER.lower()), env["DOCUMENSO_WEBHOOK_SECRET"])
    assert parse_event(hook["body"]).external_id == "it:1"

    result = service.fetch_result(session.envelope_id)
    assert result.is_completed and result.completed_at is not None
    assert set(result.documents) == {"Part 1.pdf", "Appendix.pdf"}
    for signed in result.documents.values():
        _assert_sealed(signed)
        with pymupdf.open(stream=signed, filetype="pdf") as doc:
            text = doc[0].get_text()
            assert "Name: Jane Signer" in text and "Place: Funchal" in text
            # The signing certificate page is appended to each document.
            assert "Signing Certificate" in doc[doc.page_count - 1].get_text()
    assert result.audit_log_pdf.startswith(b"%PDF")
    assert result.certificate_pdf.startswith(b"%PDF")

    # The app has stored everything: delete it from Documenso, then purge.
    assert service.cancel(session.envelope_id)
    with psycopg.connect(env["DOCUMENSO_DATABASE_URL"]) as conn:
        data_ids = [
            r[0]
            for r in conn.execute(
                'SELECT "documentDataId" FROM "EnvelopeItem" WHERE "envelopeId" = %s',
                (session.envelope_id,),
            )
        ]
    assert len(data_ids) == 2  # soft-deleted only: files still there

    report = purge(env["DOCUMENSO_DATABASE_URL"], older_than_days=0)
    assert report.envelopes >= 1 and report.document_data >= 2
    with psycopg.connect(env["DOCUMENSO_DATABASE_URL"]) as conn:
        left = conn.execute(
            'SELECT count(*) FROM "DocumentData" WHERE id = ANY(%s)', (data_ids,)
        ).fetchone()[0]
        envelopes = conn.execute(
            'SELECT count(*) FROM "Envelope" WHERE id = %s', (session.envelope_id,)
        ).fetchone()[0]
    assert left == 0 and envelopes == 0


def test_cancel_pending_session(service):
    session = service.start(
        title="Cancelled",
        signer=Signer("Jane Signer", "jane.signer@example.test"),
        documents=[_document("Form.pdf", "FORM")],
    )
    assert service.cancel(session.envelope_id)
    with pytest.raises(DocumensoNotFound):
        service.client.get_envelope(session.envelope_id)
    # The embed link is dead too.
    page = httpx.get(session.embed_url.split("#")[0], follow_redirects=True)
    assert "Sign Document" not in page.text


def test_purge_keeps_pending_and_recent(env, service):
    session = service.start(
        title="Keep me",
        signer=Signer("Jane Signer", "jane.signer@example.test"),
        documents=[_document("Form.pdf", "FORM")],
    )
    try:
        purge(env["DOCUMENSO_DATABASE_URL"], older_than_days=0, pending_older_than_days=1)
        assert service.fetch_result(session.envelope_id).status == "PENDING"
    finally:
        service.cancel(session.envelope_id)


def _assert_sealed(pdf: bytes) -> None:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    reader = PdfFileReader(io.BytesIO(pdf))
    sigs = reader.embedded_signatures
    assert len(sigs) == 1
    status = validate_pdf_signature(sigs[0], ValidationContext(allow_fetching=False))
    assert status.intact and status.valid
    assert status.coverage.name == "ENTIRE_FILE"
    assert str(sigs[0].sig_object["/SubFilter"]) == "/ETSI.CAdES.detached"


def test_health(env):
    health = httpx.get(f"{env['DOCUMENSO_URL']}/api/health").json()
    assert health["status"] == "ok"
    assert json.dumps(health["checks"]).count('"ok"') >= 2
