#!/usr/bin/env bash
# Generate a self-signed PKCS#12 signing certificate for Documenso.
#
# Run it on YOUR machine; the private key should never be committed or pasted
# into chat. Output:
#   cert.p12        - the certificate + private key, passphrase protected
#   cert.p12.b64    - the same file base64-encoded, ready to paste into the
#                     NEXT_PRIVATE_SIGNING_LOCAL_FILE_CONTENTS env var on Render
#
# Usage:
#   ./make-selfsigned-cert.sh "Euromar" "PT" [days]
#   SIGNING_PASSPHRASE=... ./make-selfsigned-cert.sh "Euromar" "PT"
#
# Later, to switch to a certificate from a qualified trust service provider,
# replace cert.p12 with the one they issue (same env vars, no code change).
set -euo pipefail

ORG="${1:-Euromar}"
COUNTRY="${2:-PT}"
DAYS="${3:-3650}"
OUT_DIR="${OUT_DIR:-.}"

if [[ -z "${SIGNING_PASSPHRASE:-}" ]]; then
  read -r -s -p "Passphrase for cert.p12: " SIGNING_PASSPHRASE
  echo
fi
if [[ -z "$SIGNING_PASSPHRASE" ]]; then
  echo "A non-empty passphrase is required." >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -days "$DAYS" \
  -keyout "$WORK/key.pem" -out "$WORK/cert.pem" \
  -subj "/C=${COUNTRY}/O=${ORG}/CN=${ORG} Document Signing" \
  -addext "keyUsage=critical,digitalSignature,nonRepudiation" \
  -addext "extendedKeyUsage=emailProtection,1.3.6.1.4.1.311.10.3.12" \
  2>/dev/null

# -legacy keeps the p12 readable by older PKCS#12 parsers; harmless otherwise.
openssl pkcs12 -export \
  -inkey "$WORK/key.pem" -in "$WORK/cert.pem" \
  -name "${ORG} Document Signing" \
  -passout "pass:${SIGNING_PASSPHRASE}" \
  -out "$OUT_DIR/cert.p12" 2>/dev/null \
  || openssl pkcs12 -export -legacy \
    -inkey "$WORK/key.pem" -in "$WORK/cert.pem" \
    -name "${ORG} Document Signing" \
    -passout "pass:${SIGNING_PASSPHRASE}" \
    -out "$OUT_DIR/cert.p12"

base64 < "$OUT_DIR/cert.p12" | tr -d '\n' > "$OUT_DIR/cert.p12.b64"

echo "Created $OUT_DIR/cert.p12 and $OUT_DIR/cert.p12.b64 (valid ${DAYS} days)."
openssl x509 -in "$WORK/cert.pem" -noout -subject -enddate
