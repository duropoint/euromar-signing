# Compliance statement (eIDAS / GDPR)

## Signature level

Documents signed through Euromar e-signing carry an **eIDAS simple
electronic signature (SES)** by the signer, and the document is **sealed** by
the platform with a PAdES signature (`ETSI.CAdES.detached`) covering the
whole file.

- eIDAS Art. 25(1): an electronic signature shall not be denied legal effect
  or admissibility as evidence solely because it is electronic or does not
  meet the requirements for qualified electronic signatures.
- It is **not** an advanced (AES) or qualified (QES) signature. Only a QES has
  the equivalent legal effect of a handwritten signature (Art. 25(2);
  Portugal: DL 12/2021). Documents that legally require a QES or a wet
  signature must keep using one.

Note: Documenso's signing confirmation dialog states that the signature
"holds the same legal validity as a handwritten signature". That wording is
upstream and broader than the SES level above; this statement prevails.

## Evidence kept per signed document (by the app)

1. The sealed PDF (any PAdES validator: Adobe Reader, EU DSS demo).
2. The signing-certificate page appended to it: signer name/email, IP,
   user agent, sent/viewed/signed timestamps, signature ID.
3. The full audit-log PDF and the certificate PDF from Documenso.
4. The app's own audit trail: authenticated user, organisation, timestamps,
   file hashes.

Signers are authenticated users of the app (not anonymous email links),
which strengthens attribution beyond a typical SES.

## Certificate

Currently self-signed (Euromar). Integrity is verifiable; identity is shown
as "unknown" by PDF readers. Upgrade path: an organisation seal certificate
from a QTSP on the EU Trusted List (e.g. Multicert, DigitalSign) and a
qualified timestamp — configuration only. QES for signers would need
Documenso's commercial CSC integration or a Chave Móvel Digital integration.

## Data protection

- Hosting: Render, Frankfurt (EU). Documenso instance and database are
  self-hosted; no third-party e-signature processor.
- Minimisation: signers receive no emails from Documenso; finished envelopes,
  their PDFs and audit rows are purged after 30 days; apps hold the record.
- Telemetry disabled (`DOCUMENSO_DISABLE_TELEMETRY=true`). Documenso still
  performs a licence check call to license.documenso.com without document data.
- Record of processing: add "e-signature of application forms" with Render
  as hosting processor.
