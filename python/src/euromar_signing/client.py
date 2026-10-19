"""Thin, typed wrapper over the Documenso v2 REST API (`/api/v2`).

Only the calls an embedding app needs: create an envelope from uploaded PDFs
with one signer and its signature fields, distribute it without any email,
read it back, download the sealed results, and delete it.

Pinned against Documenso v2.20.0 (see deploy/render.yaml). Response parsing
reads only the keys listed here so additive API changes don't break callers.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from typing import Any

import httpx

from .models import SignatureBox, Signer

logger = logging.getLogger(__name__)

# Every notification Documenso can send. Embedding apps deliver the signing
# link themselves and own all user-facing mail, so all are switched off.
NO_EMAILS = {
    "recipientSigningRequest": False,
    "recipientRemoved": False,
    "recipientSigned": False,
    "documentPending": False,
    "documentCompleted": False,
    "documentDeleted": False,
    "ownerDocumentCompleted": False,
    "ownerRecipientExpired": False,
    "ownerDocumentCreated": False,
}

_RETRY_STATUS = {429, 502, 503, 504}


class DocumensoError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class DocumensoNotFound(DocumensoError):
    pass


class DocumensoClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        timeout: float = 60.0,
        max_attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        if not base_url or not api_token:
            raise ValueError("DocumensoClient needs a base_url and an api_token")
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self._http = httpx.Client(
            base_url=f"{self.base_url}/api/v2",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> DocumensoClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- transport ---------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                logger.warning(
                    "Documenso %s %s failed (%s), attempt %d", method, path, exc, attempt
                )
            else:
                if resp.status_code not in _RETRY_STATUS or attempt == self.max_attempts:
                    return self._raise_for_status(resp, method, path)
                logger.warning(
                    "Documenso %s %s returned %d, attempt %d",
                    method,
                    path,
                    resp.status_code,
                    attempt,
                )
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 30))
                    continue
            time.sleep(min(2 ** (attempt - 1), 8))
        raise DocumensoError(f"Documenso {method} {path} unreachable: {last_exc}") from last_exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response, method: str, path: str) -> httpx.Response:
        if resp.is_success:
            return resp
        body = resp.text[:2000]
        msg = f"Documenso {method} {path} -> {resp.status_code}: {body[:300]}"
        if resp.status_code == 404:
            raise DocumensoNotFound(msg, resp.status_code, body)
        raise DocumensoError(msg, resp.status_code, body)

    # -- envelopes ---------------------------------------------------------

    def create_envelope(
        self,
        *,
        title: str,
        documents: Sequence[tuple[str, bytes]],
        signer: Signer,
        fields: Sequence[tuple[int, SignatureBox]],
        external_id: str | None = None,
        timezone: str = "Europe/Lisbon",
        language: str = "en",
    ) -> str:
        """Create a DRAFT envelope; returns its id.

        `documents` is a list of (filename, pdf bytes); each becomes one
        envelope item, in order. `fields` is a list of (document index,
        SignatureBox) for the single signer.
        """
        if not documents:
            raise ValueError("at least one document is required")
        payload: dict[str, Any] = {
            "title": title,
            "type": "DOCUMENT",
            "meta": {
                "timezone": timezone,
                "language": language,
                "distributionMethod": "NONE",
                "signingOrder": "PARALLEL",
                "emailSettings": NO_EMAILS,
                # Signers draw or type; no uploaded signature images.
                "uploadSignatureEnabled": False,
            },
            "recipients": [
                {
                    "email": signer.email,
                    "name": signer.name,
                    "role": "SIGNER",
                    "fields": [
                        {
                            "type": "SIGNATURE",
                            "identifier": doc_index,
                            "page": box.page,
                            "positionX": box.x,
                            "positionY": box.y,
                            "width": box.width,
                            "height": box.height,
                        }
                        for doc_index, box in fields
                    ],
                }
            ],
        }
        if external_id:
            payload["externalId"] = external_id
        files = [("files", (name, pdf, "application/pdf")) for name, pdf in documents]
        resp = self._request(
            "POST", "/envelope/create", data={"payload": json.dumps(payload)}, files=files
        )
        return resp.json()["id"]

    def distribute(self, envelope_id: str) -> list[dict]:
        """Move the envelope to PENDING without sending mail. Returns the
        recipients: [{id, name, email, token, role, signingUrl}, ...]."""
        resp = self._request(
            "POST",
            "/envelope/distribute",
            json={
                "envelopeId": envelope_id,
                "meta": {"distributionMethod": "NONE", "emailSettings": NO_EMAILS},
            },
        )
        return resp.json().get("recipients", [])

    def get_envelope(self, envelope_id: str) -> dict:
        return self._request("GET", f"/envelope/{envelope_id}").json()

    def download_item(self, envelope_item_id: str, version: str = "signed") -> bytes:
        return self._request(
            "GET", f"/envelope/item/{envelope_item_id}/download", params={"version": version}
        ).content

    def download_audit_log(self, envelope_id: str) -> bytes:
        return self._request("GET", f"/envelope/{envelope_id}/audit-log/download").content

    def download_certificate(self, envelope_id: str) -> bytes:
        return self._request("GET", f"/envelope/{envelope_id}/certificate/download").content

    def delete_envelope(self, envelope_id: str) -> None:
        """Delete an envelope. Pending ones are removed outright; completed
        ones are only soft-deleted by Documenso (the purge job cleans up)."""
        self._request("POST", "/envelope/delete", json={"envelopeId": envelope_id})
