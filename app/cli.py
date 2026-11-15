"""Command line: export and reset.

    python -m app.cli export [--to FOLDER]
    python -m app.cli reset --yes [--from FOLDER]
"""
import argparse
import sys
from pathlib import Path

from . import db, logic


def cmd_export(args) -> int:
    folder = db.export_to(args.to or db.default_export_folder())
    print(f"Exported to {folder}")
    return 0


def cmd_reset(args) -> int:
    src = args.src or db.DATA_DIR
    if not args.yes:
        print(f"Reset replaces ALL data with the CSV files in {src}.")
        print("A backup of the current data is written first.")
        print("Nothing was changed. Run again with --yes to confirm.")
        return 1
    backup, n_db, n_used = db.reset_from(src)
    created = logic.sync()
    print(f"Backup saved to {backup}")
    print(f"Imported {n_db} task_db rows and {n_used} task_used rows from {src}")
    print(f"Sync created {created} new task_used rows")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export", help="Write both tables to CSV files")
    p_export.add_argument("--to", type=Path, help="Target folder (default: data/exports/<timestamp>)")
    p_export.set_defaults(func=cmd_export)

    p_reset = sub.add_parser("reset", help="Replace all data with CSV files")
    p_reset.add_argument("--yes", action="store_true", help="Confirm the reset")
    p_reset.add_argument("--from", dest="src", type=Path,
                         help="Folder holding task_db.csv and task_used.csv (default: data/)")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    db.pool.open(wait=True)
    try:
        db.init_schema()
        return args.func(args)
    except db.CsvError as e:
        print(f"Import failed. Nothing was changed.\n  {e}", file=sys.stderr)
        return 2
    finally:
        db.pool.close()


if __name__ == "__main__":
    sys.exit(main())
