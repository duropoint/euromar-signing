#!/usr/bin/env bash
# Start the local Documenso stack and seed it for development / CI:
# an admin account, an API token and a webhook for its team.
#
# LOCAL ONLY: it writes straight into Documenso's database. Production is set
# up by hand through the UI (docs/ONBOARDING_AN_APP.md).
#
# Idempotent. Writes deploy/.local/env with:
#   DOCUMENSO_URL, DOCUMENSO_API_TOKEN, DOCUMENSO_WEBHOOK_SECRET,
#   DOCUMENSO_DATABASE_URL, DOCUMENSO_ADMIN_EMAIL, DOCUMENSO_ADMIN_PASSWORD
#
# Env overrides:
#   DOCUMENSO_PORT (3005)  WEBHOOK_URL (http://host.docker.internal:8765/documenso/webhook)
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${DOCUMENSO_PORT:-3005}"
DB_PORT="${DOCUMENSO_DB_PORT:-54329}"
URL="http://localhost:${PORT}"
WEBHOOK_URL="${WEBHOOK_URL:-http://host.docker.internal:8765/documenso/webhook}"
ADMIN_EMAIL="admin@localhost.test"
ADMIN_PASSWORD="LocalAdmin!2345"
API_TOKEN="api_localdevtoken0001"
WEBHOOK_SECRET="local-webhook-secret"

mkdir -p .local
if [[ ! -f .local/cert.p12 ]]; then
  OUT_DIR=.local SIGNING_PASSPHRASE=local ./scripts/make-selfsigned-cert.sh "Euromar Local" PT 365
fi
chmod 644 .local/cert.p12

docker compose up -d

echo -n "Waiting for Documenso at $URL "
for _ in $(seq 1 120); do
  if curl -fsS "$URL/api/health" >/dev/null 2>&1; then echo " up"; break; fi
  echo -n "."; sleep 2
done
curl -fsS "$URL/api/health" >/dev/null

psql_exec() {
  docker compose exec -T db psql -U documenso -d documenso -v ON_ERROR_STOP=1 -tAc "$1"
}

# The auth API rejects cross-origin mutations; send the app's own Origin.
curl -sS -o /dev/null -X POST "$URL/api/auth/email-password/signup" \
  -H "Origin: $URL" -H 'content-type: application/json' \
  -d "{\"name\":\"Local Admin\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" || true

USER_ID="$(psql_exec "SELECT id FROM \"User\" WHERE email = '$ADMIN_EMAIL'")"
[[ -n "$USER_ID" ]] || { echo "admin signup failed" >&2; exit 1; }
TEAM_ID="$(psql_exec "SELECT t.id FROM \"Team\" t JOIN \"Organisation\" o ON o.id = t.\"organisationId\" WHERE o.\"ownerUserId\" = $USER_ID ORDER BY t.id LIMIT 1")"

TOKEN_HASH="$(printf %s "$API_TOKEN" | sha512sum | cut -d' ' -f1)"
psql_exec "
UPDATE \"User\" SET \"emailVerified\" = COALESCE(\"emailVerified\", now()) WHERE id = $USER_ID;
DELETE FROM \"ApiToken\" WHERE token = '$TOKEN_HASH';
INSERT INTO \"ApiToken\" (name, token, algorithm, \"userId\", \"teamId\")
  VALUES ('local-dev', '$TOKEN_HASH', 'SHA512', $USER_ID, $TEAM_ID);
DELETE FROM \"Webhook\" WHERE \"teamId\" = $TEAM_ID;
INSERT INTO \"Webhook\" (id, \"webhookUrl\", \"eventTriggers\", secret, enabled, \"userId\", \"teamId\", \"updatedAt\")
  VALUES ('local-webhook', '$WEBHOOK_URL',
          ARRAY['DOCUMENT_COMPLETED','DOCUMENT_REJECTED','DOCUMENT_CANCELLED']::\"WebhookTriggerEvents\"[],
          '$WEBHOOK_SECRET', true, $USER_ID, $TEAM_ID, now());
" >/dev/null

cat > .local/env <<EOF
DOCUMENSO_URL=$URL
DOCUMENSO_API_TOKEN=$API_TOKEN
DOCUMENSO_WEBHOOK_SECRET=$WEBHOOK_SECRET
DOCUMENSO_DATABASE_URL=postgresql://documenso:documenso@localhost:${DB_PORT}/documenso
DOCUMENSO_ADMIN_EMAIL=$ADMIN_EMAIL
DOCUMENSO_ADMIN_PASSWORD=$ADMIN_PASSWORD
EOF

echo "Seeded team $TEAM_ID. Settings written to deploy/.local/env:"
cat .local/env
echo "Mail UI: http://localhost:${MAILPIT_UI_PORT:-8025}"
