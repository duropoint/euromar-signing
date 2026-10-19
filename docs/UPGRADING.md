# Upgrading Documenso

The image tag is pinned in two places — keep them identical:
`render.yaml` and `deploy/docker-compose.yml`.

1. Read the release notes between the current and target version (API v2,
   embed, Prisma schema changes to `Envelope`, `EnvelopeItem`,
   `DocumentData`, `DocumentMeta`, `DocumentAuditLog` used by the purge job).
2. Bump the tag in both files on a branch.
3. Locally: `docker compose -f deploy/docker-compose.yml down -v`,
   `deploy/scripts/bootstrap-local.sh`, `pytest -m integration`. CI runs the
   same. Fix the client / signing bot / purge SQL if anything moved.
4. Merge → Render redeploys (migrations run automatically on boot).
5. Sign one test envelope in production.

Rollback: re-pin the previous tag. Prisma migrations are forward-only, so
for a major jump take a manual Postgres backup first.
