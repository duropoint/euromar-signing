# Integrating an app

## Flow

1. **Start** (backend, when the user clicks *Sign*):
   prefill → place signature boxes → `SigningService.start()` → persist
   `envelope_id` + `embed_url` as a *pending signature* → return `embed_url`.
2. **Sign** (frontend): show `embed_url` in an iframe
   (`frontend/signing-embed.ts`). On `document-completed`, call your backend.
3. **Complete** (backend), from *either* the webhook or the frontend call —
   whichever arrives first, idempotently:
   `fetch_result(envelope_id)` → if `is_completed`, store
   `result.documents`, `audit_log_pdf`, `certificate_pdf`; mark done;
   `cancel(envelope_id)` to remove it from Documenso.
4. **Abandon** (data changed, user cancels): `cancel(envelope_id)`; the old
   embed link stops working.

Never trust the iframe message or the webhook body alone: both only trigger
step 3, which re-reads the envelope with the API token.

## Backend

```python
from euromar_signing import (
    SigningService, SigningDocument, Signer, TextStamp, box_near_text, stamp_text,
    verify_secret, parse_event, SECRET_HEADER,
)

svc = SigningService.from_settings(settings.DOCUMENSO_URL, settings.DOCUMENSO_API_TOKEN)

# Prefill values the app already knows (name, date, place): stamped into the
# PDF before signing, so the signer only signs and the seal covers them.
pdf = stamp_text(pdf, [TextStamp(page_index=0, x=72, y=700, text="Name: Jane Signer")])

# Signature box under a caption printed on the form (falls back to the
# bottom of the last page if the caption is missing).
box = box_near_text(pdf, "Signature:", dy=4, width=180, height=45)

session = svc.start(
    title="CPP-2026-0042 — ISM side",
    signer=Signer(user.full_name, user.email),
    documents=[SigningDocument("cpp_part1.pdf", pdf, [box])],
    external_id="cpp:app:42:ISM",   # comes back in webhooks
)
```

Several documents in one session = one signing session: the signer types or
draws once and clicks each signature field to apply it.

Webhook view (Django example):

```python
def documenso_webhook(request):
    if not verify_secret(request.headers.get(SECRET_HEADER), settings.DOCUMENSO_WEBHOOK_SECRET):
        return HttpResponse(status=401)
    event = parse_event(request.body)
    pending = PendingSignature.objects.filter(external_submission_id=event.envelope_id).first()
    if pending:
        complete_pending_signature(pending)   # calls svc.fetch_result(...)
    return HttpResponse(status=200)           # 200 even if unknown: stops retries
```

## Frontend

Copy `frontend/signing-embed.ts`; see `SigningEmbed.example.tsx`. Allow the
Documenso origin in your CSP `frame-src` if you set one.

## Coordinates

`SignatureBox` uses Documenso units: page is 1-based; x/y/width/height are
percentages of the page from the top-left. `to_signature_box()` converts from
PDF points; `box_near_text()` does it for you.

## Local development

`deploy/scripts/bootstrap-local.sh` prints `DOCUMENSO_URL` / token / secret
for a local instance; its webhook points at
`http://host.docker.internal:8765/documenso/webhook` (override with
`WEBHOOK_URL=… bootstrap-local.sh`). Without a reachable webhook, the
frontend's completion call (step 3) still completes the flow.
