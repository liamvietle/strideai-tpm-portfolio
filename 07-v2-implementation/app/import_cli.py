from __future__ import annotations

import argparse
from pathlib import Path

from app.ingestion import parse_garmin_summary_csv, parse_tcx
from app.models import ImportSummary
from app.storage import init_db, upsert_activities


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Garmin/Strava activity exports into StrideAI.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--athlete-id", required=True)
    parser.add_argument("--format", required=True, choices=["tcx", "garmin-csv"])
    parser.add_argument("--source", default="garmin", choices=["garmin", "strava", "other"])
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    content = Path(args.file).read_text(encoding="utf-8-sig")
    if args.format == "tcx":
        records = parse_tcx(content, athlete_id=args.athlete_id, source=args.source)
    else:
        records = parse_garmin_summary_csv(content, athlete_id=args.athlete_id)

    init_db(args.db)
    inserted, updated = upsert_activities(records, args.db)
    summary = ImportSummary(
        source=args.source if args.format == "tcx" else "garmin",
        format=args.format,
        parsed=len(records),
        inserted=inserted,
        updated=updated,
        skipped=max(0, len(records) - inserted - updated),
    )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
