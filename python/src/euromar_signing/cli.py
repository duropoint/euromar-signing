"""`euromar-signing` command line (used by the Render cron job)."""

from __future__ import annotations

import argparse
import logging
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="euromar-signing")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("purge", help="delete finished envelopes and their files from Documenso")
    p.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Documenso Postgres URL (default: $DATABASE_URL)",
    )
    p.add_argument("--older-than-days", type=int, default=30)
    p.add_argument("--pending-older-than-days", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "purge":
        if not args.database_url:
            parser.error("--database-url or $DATABASE_URL is required")
        from .purge import purge

        report = purge(
            args.database_url,
            older_than_days=args.older_than_days,
            pending_older_than_days=args.pending_older_than_days,
            dry_run=args.dry_run,
        )
        print(
            f"{'[dry run] ' if report.dry_run else ''}purged envelopes={report.envelopes} "
            f"files={report.document_data} meta={report.document_meta} "
            f"audit_logs={report.audit_logs}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
