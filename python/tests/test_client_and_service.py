import json

import httpx
import pytest
import respx

from euromar_signing import (
    DocumensoClient,
    DocumensoError,
    SignatureBox,
    Signer,
    SigningDocument,
    SigningService,
)

BASE = "https://sign.test"
API = f"{BASE}/api/v2"
BOX = SignatureBox(page=1, x=10, y=80, width=30, height=6)


@pytest.fixture
def client():
    c = DocumensoClient(BASE, "api_x", max_attempts=2)
    yield c
    c.close()


def _envelope(status="PENDING", completed_at=None):
    return {
        "id": "envelope_1",
        "status": status,
        "completedAt": completed_at,
        "envelopeItems": [
            {"id": "item_b", "title": "b.pdf", "order": 2},
            {"id": "item_a", "title": "a.pdf", "order": 1},
        ],
    }


@respx.mock
def test_create_envelope_payload(client, pdf_factory):
    route = respx.post(f"{API}/envelope/create").mock(
        return_value=httpx.Response(200, json={"id": "envelope_1"})
    )
    eid = client.create_envelope(
        title="T",
        documents=[("a.pdf", pdf_factory("A")), ("b.pdf", pdf_factory("B"))],
        signer=Signer("Jane", "jane@x.test"),
        fields=[(0, BOX), (1, BOX)],
        external_id="app:1",
    )
    assert eid == "envelope_1"
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer api_x"
    body = req.content.decode("latin-1")
    payload = json.loads(body.split('name="payload"\r\n\r\n', 1)[1].split("\r\n--", 1)[0])
    assert payload["externalId"] == "app:1"
    assert payload["meta"]["distributionMethod"] == "NONE"
    assert not any(payload["meta"]["emailSettings"].values())
    fields = payload["recipients"][0]["fields"]
    assert [f["identifier"] for f in fields] == [0, 1]
    assert fields[0]["positionX"] == 10 and fields[0]["page"] == 1
    assert body.count('name="files"') == 2


@respx.mock
def test_retries_on_429_then_succeeds(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    respx.get(f"{API}/envelope/envelope_1").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json=_envelope()),
        ]
    )
    assert client.get_envelope("envelope_1")["status"] == "PENDING"


@respx.mock
def test_error_raises(client):
    respx.get(f"{API}/envelope/nope").mock(return_value=httpx.Response(400, text="bad"))
    with pytest.raises(DocumensoError) as exc:
        client.get_envelope("nope")
    assert exc.value.status_code == 400


@respx.mock
def test_service_start_builds_session(client, pdf_factory):
    respx.post(f"{API}/envelope/create").mock(
        return_value=httpx.Response(200, json={"id": "envelope_1"})
    )
    respx.post(f"{API}/envelope/distribute").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "recipients": [
                    {"email": "JANE@x.test", "token": "tok", "signingUrl": f"{BASE}/sign/tok"}
                ],
            },
        )
    )
    respx.get(f"{API}/envelope/envelope_1").mock(return_value=httpx.Response(200, json=_envelope()))
    svc = SigningService(client)
    session = svc.start(
        title="T",
        signer=Signer("Jane", "jane@x.test"),
        documents=[
            SigningDocument("a.pdf", pdf_factory("A"), [BOX]),
            SigningDocument("b.pdf", pdf_factory("B"), [BOX]),
        ],
    )
    assert session.envelope_id == "envelope_1"
    assert session.signing_token == "tok"
    assert session.embed_url.startswith(f"{BASE}/embed/sign/tok#")
    assert session.items == {"a.pdf": "item_a", "b.pdf": "item_b"}


@respx.mock
def test_service_start_cleans_up_on_failure(client, pdf_factory):
    respx.post(f"{API}/envelope/create").mock(
        return_value=httpx.Response(200, json={"id": "envelope_1"})
    )
    respx.post(f"{API}/envelope/distribute").mock(return_value=httpx.Response(400, text="x"))
    delete = respx.post(f"{API}/envelope/delete").mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(DocumensoError):
        SigningService(client).start(
            title="T",
            signer=Signer("Jane", "jane@x.test"),
            documents=[SigningDocument("a.pdf", pdf_factory("A"), [BOX])],
        )
    assert delete.called


def test_service_start_validates_documents(client, pdf_factory):
    svc = SigningService(client)
    with pytest.raises(ValueError):
        svc.start(
            title="T",
            signer=Signer("J", "j@x"),
            documents=[SigningDocument("a.pdf", b"", [BOX]), SigningDocument("a.pdf", b"", [BOX])],
        )
    with pytest.raises(ValueError):
        svc.start(
            title="T", signer=Signer("J", "j@x"), documents=[SigningDocument("a.pdf", b"", [])]
        )


@respx.mock
def test_fetch_result_pending_downloads_nothing(client):
    respx.get(f"{API}/envelope/envelope_1").mock(return_value=httpx.Response(200, json=_envelope()))
    result = SigningService(client).fetch_result("envelope_1")
    assert result.status == "PENDING"
    assert not result.is_completed and not result.is_final
    assert result.documents == {}


@respx.mock
def test_fetch_result_completed_downloads_everything(client):
    respx.get(f"{API}/envelope/envelope_1").mock(
        return_value=httpx.Response(200, json=_envelope("COMPLETED", "2026-10-19T11:25:52.282Z"))
    )
    respx.get(f"{API}/envelope/item/item_a/download").mock(
        return_value=httpx.Response(200, content=b"%PDF-a")
    )
    respx.get(f"{API}/envelope/item/item_b/download").mock(
        return_value=httpx.Response(200, content=b"%PDF-b")
    )
    respx.get(f"{API}/envelope/envelope_1/audit-log/download").mock(
        return_value=httpx.Response(200, content=b"%PDF-audit")
    )
    respx.get(f"{API}/envelope/envelope_1/certificate/download").mock(
        return_value=httpx.Response(200, content=b"%PDF-cert")
    )
    result = SigningService(client).fetch_result("envelope_1")
    assert result.is_completed
    assert result.completed_at.year == 2026 and result.completed_at.tzinfo is not None
    assert result.documents == {"a.pdf": b"%PDF-a", "b.pdf": b"%PDF-b"}
    assert result.audit_log_pdf == b"%PDF-audit"
    assert result.certificate_pdf == b"%PDF-cert"


@respx.mock
def test_cancel_tolerates_missing_envelope(client):
    respx.post(f"{API}/envelope/delete").mock(return_value=httpx.Response(404, text="gone"))
    assert SigningService(client).cancel("envelope_1") is True
