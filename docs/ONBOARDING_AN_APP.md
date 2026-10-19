# Onboarding an app

Each app gets its own team, API token and webhook. 👤 = Documenso admin.

1. 👤 **Team.** Documenso → organisation *Euromar* → Teams → **Create team**,
   named after the app (e.g. `CPP`).
2. 👤 **Team settings → Document:**
   - Language: English
   - Include signing certificate: per app. **On** appends a "Signing
     Certificate" page to every signed PDF; **off** keeps the documents
     unchanged (the PAdES seal is applied either way). CPP: off.
   - Include audit log: off. Apps fetch the audit-log PDF separately
     (`SigningResult.audit_log_pdf`) and store it as the evidence record.
   - Typed + drawn signatures allowed; uploaded signatures off.
3. 👤 **API token.** Team settings → API tokens → create `<app>-production`,
   no expiry. Copy it once — it is shown only at creation.
4. 👤 **Webhook.** Team settings → Webhooks → create:
   - URL: the app's public endpoint, e.g.
     `https://cpp-frontend.onrender.com/public/documenso/webhook`
   - Events: `DOCUMENT_COMPLETED`, `DOCUMENT_REJECTED`, `DOCUMENT_CANCELLED`
   - Secret: a long random string (`openssl rand -hex 32`)
5. 👤 **App configuration** (e.g. a Render env group):

   | Variable | Value |
   |---|---|
   | `DOCUMENSO_URL` | `https://docu-euromar.onrender.com` |
   | `DOCUMENSO_API_TOKEN` | token from step 3 |
   | `DOCUMENSO_WEBHOOK_SECRET` | secret from step 4 |

6. **Smoke test** from the app's environment:

   ```python
   from euromar_signing import DocumensoClient
   DocumensoClient(URL, TOKEN).get_envelope("does-not-exist")  # -> DocumensoNotFound, not 401
   ```

Revoking an app = delete its API token (and webhook) in its team.
