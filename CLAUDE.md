# Euromar Signing — working conventions

Shared e-signing kit: Documenso deployment + `euromar_signing` Python
package + copy-in frontend helper. Used by several apps (CPP first) — keep it
app-agnostic: no CPP-specific names, form types or rules in here.

- Documenso is used **unmodified** (official image, pinned). Version lives in
  `render.yaml` and `deploy/docker-compose.yml`; bump both via `docs/UPGRADING.md`.
- `python/src/euromar_signing`: stdlib + httpx + PyMuPDF only (psycopg only
  for the optional `purge` extra). Public API is what `__init__.py` exports.
- Release: bump `version` in `python/pyproject.toml` and `__init__.py`, tag
  `vX.Y.Z`; apps pin the tag archive URL.
- Tests: `cd python && pytest` (unit, mocked). Integration against a real
  Documenso: `deploy/scripts/bootstrap-local.sh` then `pytest -m integration`.
- Lint: `ruff check . && black --check .` in `python/`.
- Never commit certificates, `.local/`, tokens or secrets.
