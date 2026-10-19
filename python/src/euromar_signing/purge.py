"""Purge finished envelopes from Documenso's database.

Why: apps copy the sealed PDFs + evidence into their own storage seconds after
completion, but Documenso keeps everything forever - deleting a completed
envelope through the API is only a soft delete, and even a hard delete leaves
the PDF blobs (DocumentData) and audit-log rows behind. This job removes them
so Documenso holds only in-flight signing sessions (data minimisation).

It works directly on Documenso's tables, so it is tied to the pinned
Documenso version: tests/test_integration.py exercises it against that image,
and UPGRADING.md says to re-run it before bumping the version.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Envelopes that are finished (or abandoned) and older than the cutoffs.
_SELECT_ENVELOPES = """
SELECT e.id
FROM "Envelope" e
WHERE e.type = 'DOCUMENT'
  AND (
        (e."deletedAt" IS NOT NULL AND e."deletedAt" < now() - make_interval(days => %(days)s))
     OR (e.status IN ('COMPLETED', 'REJECTED', 'CANCELLED')
         AND COALESCE(e."completedAt", e."updatedAt") < now() - make_interval(days => %(days)s))
     OR (e.status IN ('DRAFT', 'PENDING')
         AND e."createdAt" < now() - make_interval(days => %(pending_days)s))
  )
"""


@dataclass
class PurgeReport:
    envelopes: int = 0
    document_data: int = 0
    document_meta: int = 0
    audit_logs: int = 0
    dry_run: bool = False


def purge(
    database_url: str,
    *,
    older_than_days: int = 30,
    pending_older_than_days: int = 30,
    dry_run: bool = False,
) -> PurgeReport:
    import psycopg  # optional dependency: pip install euromar-signing[purge]

    if older_than_days < 0 or pending_older_than_days < 1:
        raise ValueError("invalid retention window")
    params = {"days": older_than_days, "pending_days": pending_older_than_days}
    report = PurgeReport(dry_run=dry_run)

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(_SELECT_ENVELOPES, params)
        envelope_ids = [r[0] for r in cur.fetchall()]
        report.envelopes = len(envelope_ids)

        if envelope_ids:
            cur.execute(
                'SELECT "documentDataId" FROM "EnvelopeItem" WHERE "envelopeId" = ANY(%s)',
                (envelope_ids,),
            )
            data_ids = [r[0] for r in cur.fetchall()]
            cur.execute(
                'SELECT "documentMetaId" FROM "Envelope" WHERE id = ANY(%s)', (envelope_ids,)
            )
            meta_ids = [r[0] for r in cur.fetchall()]

            # Envelope delete cascades to items, recipients, fields, share links...
            cur.execute('DELETE FROM "Envelope" WHERE id = ANY(%s)', (envelope_ids,))
            cur.execute('DELETE FROM "DocumentData" WHERE id = ANY(%s)', (data_ids,))
            report.document_data = cur.rowcount
            cur.execute(
                'DELETE FROM "DocumentMeta" m WHERE m.id = ANY(%s) AND NOT EXISTS '
                '(SELECT 1 FROM "Envelope" e WHERE e."documentMetaId" = m.id)',
                (meta_ids,),
            )
            report.document_meta = cur.rowcount

        # Audit rows survive their envelope (FK is SET NULL) and hold names,
        # emails and IPs; apps already keep the audit-log PDF.
        cur.execute(
            'DELETE FROM "DocumentAuditLog" WHERE "envelopeId" IS NULL '
            'AND "createdAt" < now() - make_interval(days => %(days)s)',
            params,
        )
        report.audit_logs = cur.rowcount

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    logger.info("purge %s", report)
    return report
