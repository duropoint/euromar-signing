"""High-level flow most apps need: start an embedded signing session for
one signer over N PDFs, then collect the sealed PDFs once it completes."""

from __future__ import annotations

import logging
from datetime import datetime

from .client import DocumensoClient, DocumensoError, DocumensoNotFound
from .embed import build_embed_url
from .models import Signer, SigningDocument, SigningResult, SigningSession

logger = logging.getLogger(__name__)


class SigningService:
    def __init__(self, client: DocumensoClient, *, timezone: str = "Europe/Lisbon"):
        self.client = client
        self.timezone = timezone

    @classmethod
    def from_settings(cls, base_url: str, api_token: str, **kwargs) -> SigningService:
        return cls(DocumensoClient(base_url, api_token), **kwargs)

    def start(
        self,
        *,
        title: str,
        signer: Signer,
        documents: list[SigningDocument],
        external_id: str | None = None,
        language: str = "en",
    ) -> SigningSession:
        names = [d.name for d in documents]
        if len(set(names)) != len(names):
            raise ValueError("document names must be unique within a session")
        if not all(d.signature_boxes for d in documents):
            raise ValueError("every document needs at least one signature box")

        envelope_id = self.client.create_envelope(
            title=title,
            documents=[(d.name, d.pdf) for d in documents],
            signer=signer,
            fields=[(i, box) for i, d in enumerate(documents) for box in d.signature_boxes],
            external_id=external_id,
            timezone=self.timezone,
            language=language,
        )
        try:
            recipients = self.client.distribute(envelope_id)
            recipient = next(
                r for r in recipients if r.get("email", "").lower() == signer.email.lower()
            )
            envelope = self.client.get_envelope(envelope_id)
        except Exception:
            # Don't leave an orphan draft behind.
            self.cancel(envelope_id)
            raise

        items = {
            item["title"]: item["id"]
            for item in sorted(envelope.get("envelopeItems", []), key=lambda i: i.get("order", 0))
        }
        token = recipient["token"]
        return SigningSession(
            envelope_id=envelope_id,
            signing_token=token,
            embed_url=build_embed_url(
                self.client.base_url, token, name=signer.name, email=signer.email, language=language
            ),
            signing_url=recipient.get("signingUrl") or f"{self.client.base_url}/sign/{token}",
            items=items,
        )

    def fetch_result(self, envelope_id: str, *, include_evidence: bool = True) -> SigningResult:
        """Current state of the envelope; signed PDFs (+ audit log and signing
        certificate) are downloaded only when it is COMPLETED."""
        envelope = self.client.get_envelope(envelope_id)
        completed_at = envelope.get("completedAt")
        result = SigningResult(
            envelope_id=envelope_id,
            status=envelope.get("status", ""),
            completed_at=_parse_dt(completed_at) if completed_at else None,
        )
        if not result.is_completed:
            return result
        for item in envelope.get("envelopeItems", []):
            result.documents[item["title"]] = self.client.download_item(item["id"], "signed")
        if include_evidence:
            result.audit_log_pdf = self.client.download_audit_log(envelope_id)
            result.certificate_pdf = self.client.download_certificate(envelope_id)
        return result

    def cancel(self, envelope_id: str) -> bool:
        """Best-effort delete (abandoned session, or cleanup after the app
        stored the results). Returns False if Documenso refused."""
        try:
            self.client.delete_envelope(envelope_id)
            return True
        except DocumensoNotFound:
            return True
        except DocumensoError as exc:
            logger.warning("Could not delete Documenso envelope %s: %s", envelope_id, exc)
            return False


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
