# Deploying Documenso on Render

One-time setup. 👤 = done by a person with Render / Resend access.

## 1. 👤 Signing certificate

On your own machine (never commit the output):

```
cd deploy/scripts
./make-selfsigned-cert.sh "Euromar" "PT"      # asks for a passphrase
```

You get `cert.p12` (keep it in your password manager) and `cert.p12.b64`
(paste into Render in step 2). The certificate is self-signed: signatures are
cryptographically valid and tamper-evident, but PDF readers show the signer
identity as "unknown" until it is replaced by a certificate from a qualified
trust service provider (same two env vars, no code change).

## 2. 👤 Create the Blueprint

Render dashboard → **New → Blueprint** → repo `duropoint/euromar-signing`,
branch `main`. It creates `docu-euromar`, `docu-euromar-db`,
`docu-euromar-purge`. Fill the prompted secrets:

| Variable | Value |
|---|---|
| `NEXT_PRIVATE_SIGNING_LOCAL_FILE_CONTENTS` | contents of `cert.p12.b64` |
| `NEXT_PRIVATE_SIGNING_PASSPHRASE` | the passphrase from step 1 |
| `NEXT_PRIVATE_RESEND_API_KEY` | a Resend API key for `email.eu-registry.com` |
| `NEXT_PRIVATE_SIGNING_TIMESTAMP_AUTHORITY` | leave **empty** for now (step 6) |

Wait for the deploy, then check `https://docu-euromar.onrender.com/api/health`
→ `"database":{"status":"ok"}, "certificate":{"status":"ok"}`.

## 3. 👤 First admin account

1. Open `https://docu-euromar.onrender.com/signup`; sign up with a shared
   mailbox you control (e.g. it@…), a strong password.
2. Click the verification link in the email, log in.
3. Profile → Security → enable **two-factor authentication**.

## 4. Close signup

Change `NEXT_PUBLIC_DISABLE_SIGNUP` to `"true"` in `render.yaml` (PR), merge,
Blueprint sync. Colleagues can still be invited from the organisation settings.

## 5. 👤 Organisation and one team per app

Create organisation **Euromar**, then follow
[ONBOARDING_AN_APP.md](ONBOARDING_AN_APP.md) for each app (CPP first).

## 6. Timestamp authority (optional, recommended)

Set `NEXT_PRIVATE_SIGNING_TIMESTAMP_AUTHORITY=http://timestamp.digicert.com`,
redeploy, sign one test envelope and check it completes and the PDF shows a
timestamp. If sealing fails, clear the variable again (signing still works,
just without the trusted timestamp / long-term validation data).

## Operations

- **Health:** `/api/health` (Render health check uses it).
- **Purge job:** `docu-euromar-purge` runs nightly; logs show
  `purged envelopes=… files=…`. Envelopes older than 30 days (finished, or
  pending and abandoned) are deleted with their PDFs and audit rows.
- **Backups:** Render Postgres daily backups. Nothing in Documenso is the
  system of record — apps hold the signed documents.
- **Rotating secrets:** never change `NEXT_PRIVATE_ENCRYPTION_KEY*` after
  first boot (2FA secrets and tokens are encrypted with them).
