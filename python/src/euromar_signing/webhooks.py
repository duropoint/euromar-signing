"""Inbound Documenso webhooks.

Documenso authenticates webhooks only by echoing the shared secret in the
`X-Documenso-Secret` header (no body signature). Treat a verified webhook as
a *hint*: re-read the envelope with the API token before acting on it
(SigningService.fetch_result does exactly that).
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass

SECRET_HEADER = "X-Documenso-Secret"

COMPLETED = "DOCUMENT_COMPLETED"
REJECTED = "DOCUMENT_REJECTED"
CANCELLED = "DOCUMENT_CANCELLED"
FINAL_EVENTS = (COMPLETED, REJECTED, CANCELLED)


@dataclass(frozen=True)
class WebhookEvent:
    event: str
    envelope_id: str | None
    external_id: str | None
    status: str | None


def verify_secret(received: str | None, expected: str) -> bool:
    if not expected or not received:
        return False
    return hmac.compare_digest(received.encode(), expected.encode())


def parse_event(body: bytes | str) -> WebhookEvent:
    data = json.loads(body)
    payload = data.get("payload") or {}
    return WebhookEvent(
        event=str(data.get("event", "")),
        envelope_id=payload.get("envelopeId"),
        external_id=payload.get("externalId"),
        status=payload.get("status"),
    )
