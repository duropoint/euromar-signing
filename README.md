# Euromar Signing

Embedded e-signing for Euromar apps (CPP, CSR, ...) on one self-hosted
[Documenso](https://github.com/documenso/documenso) instance.

```
 app backend ──(API token, per app)──▶  Documenso  (docu-euromar.onrender.com)
     │  ▲                                  │   │
     │  └──── webhook (hint) ──────────────┘   │ seals PDFs with our certificate
     ▼                                         │
 app frontend ──── iframe /embed/sign/<token> ─┘
```

- Each app has its **own Documenso team + API token + webhook**; teams can't
  see each other's documents.
- Apps keep the **signed PDFs, audit log and signing certificate in their own
  storage**. Documenso only holds in-flight sessions; a nightly job purges the rest.
- Signers never get Documenso emails or accounts: the app shows the signing
  page in an iframe, behind its own login.
- Result: PAdES (`ETSI.CAdES.detached`) seal over the whole file, plus a
  signing-certificate page. Legal level: eIDAS **simple electronic signature**
  (see [docs/COMPLIANCE.md](docs/COMPLIANCE.md)).

## What's here

| Path | What |
|---|---|
| `render.yaml` | Render Blueprint: Documenso (pinned image), its Postgres, purge cron |
| `deploy/` | Local Docker stack, cert generator, local bootstrap script, env reference |
| `python/` | `euromar_signing` package: API client, PDF placement/prefill, embed URL, webhook check, purge CLI |
| `frontend/` | Copy-in TS helper for the iframe's postMessage events + reference React component |
| `docs/` | Deploy, onboarding an app, integration guide, compliance, upgrading |

## Use it from an app (Python)

```
# requirements.txt — pinned tag, no git needed in the image
euromar-signing @ https://github.com/duropoint/euromar-signing/archive/refs/tags/v0.1.0.tar.gz#subdirectory=python
```

```python
from euromar_signing import SigningService, SigningDocument, Signer, box_near_text

svc = SigningService.from_settings(DOCUMENSO_URL, DOCUMENSO_API_TOKEN)
session = svc.start(
    title="CPP-2026-0042 ISM",
    signer=Signer("Jane Signer", "jane@ship.example"),
    documents=[SigningDocument("cpp_part1.pdf", pdf, [box_near_text(pdf, "Signature:")])],
    external_id="cpp:application:42:ISM",
)
# -> give session.embed_url to the browser; keep session.envelope_id

result = svc.fetch_result(session.envelope_id)   # on webhook / reconcile
if result.is_completed:
    store(result.documents, result.audit_log_pdf, result.certificate_pdf)
    svc.cancel(session.envelope_id)               # drop it from Documenso
```

Full guide: [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Develop

```
deploy/scripts/bootstrap-local.sh          # Documenso + Postgres + Mailpit, seeded
python -m venv .venv && .venv/bin/pip install -e "python[dev]"
cd python && ../.venv/bin/pytest           # unit tests
../.venv/bin/pytest -m integration         # real Documenso: sign via the embed, verify seal, purge
```

## Licences

Our code: MIT. Documenso is AGPL-3.0 and is used **unmodified** as the
official Docker image. If you ever modify Documenso itself, the AGPL
requires publishing those modifications. Enterprise (`packages/ee`) features
are not used.
