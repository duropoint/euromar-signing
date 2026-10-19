"""Plain data types shared by the client, the PDF helpers and the service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Signer:
    name: str
    email: str


@dataclass(frozen=True)
class SignatureBox:
    """Where a signature field goes, in Documenso units.

    `page` is 1-based; x/y/width/height are percentages (0-100) of the page,
    measured from the top-left corner.
    """

    page: int
    x: float
    y: float
    width: float
    height: float


@dataclass
class SigningDocument:
    """One PDF to sign. `name` must be unique within a session; it is how the
    signed copy is handed back (see SigningResult.documents)."""

    name: str
    pdf: bytes
    signature_boxes: list[SignatureBox] = field(default_factory=list)


@dataclass(frozen=True)
class SigningSession:
    envelope_id: str
    signing_token: str
    embed_url: str
    signing_url: str
    # document name -> Documenso envelope item id
    items: dict[str, str]


class EnvelopeStatus:
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class SigningResult:
    envelope_id: str
    status: str
    completed_at: datetime | None
    # document name -> signed PDF bytes (only when status is COMPLETED)
    documents: dict[str, bytes] = field(default_factory=dict)
    audit_log_pdf: bytes | None = None
    certificate_pdf: bytes | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == EnvelopeStatus.COMPLETED

    @property
    def is_final(self) -> bool:
        return self.status in (
            EnvelopeStatus.COMPLETED,
            EnvelopeStatus.REJECTED,
            EnvelopeStatus.CANCELLED,
        )
