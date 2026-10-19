"""Embedded e-signing for Euromar apps on a self-hosted Documenso instance."""

from .client import DocumensoClient, DocumensoError, DocumensoNotFound
from .embed import build_embed_url
from .models import (
    EnvelopeStatus,
    SignatureBox,
    Signer,
    SigningDocument,
    SigningResult,
    SigningSession,
)
from .pdf import Anchor, TextStamp, box_near_text, find_text, stamp_text, to_signature_box
from .service import SigningService
from .webhooks import SECRET_HEADER, WebhookEvent, parse_event, verify_secret

__version__ = "0.1.0"

__all__ = [
    "Anchor",
    "DocumensoClient",
    "DocumensoError",
    "DocumensoNotFound",
    "EnvelopeStatus",
    "SECRET_HEADER",
    "SignatureBox",
    "Signer",
    "SigningDocument",
    "SigningResult",
    "SigningService",
    "SigningSession",
    "TextStamp",
    "WebhookEvent",
    "box_near_text",
    "build_embed_url",
    "find_text",
    "parse_event",
    "stamp_text",
    "to_signature_box",
    "verify_secret",
]
