"""
Quick validation harness for deterministic ingestion.

Usage:
  python scripts/validate_ingest.py --file "C:\\path\\to\\file.xlsx" --strict
"""
import argparse
import asyncio
from pathlib import Path

from app.services import file_parser as fp
from app.database import AsyncSessionLocal
from app.services.schema_registry_db import validate_schema_db


async def main():
    parser = argparse.ArgumentParser(description="Validate and parse a financial upload deterministically.")
    parser.add_argument("--file", required=True, help="Path to .xlsx/.xls/.csv file")
    parser.add_argument("--strict", action="store_true", help="Enable strict parsing")
    parser.add_argument("--sample-rows", type=int, default=50, help="Rows to sample per sheet for schema validation")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    content = file_path.read_bytes()

    async with AsyncSessionLocal() as db:
        validation = await validate_schema_db(file_path.name, content, db, args.sample_rows)
    print("Schema validation:", "OK" if validation.ok else "FAILED")
    print("File type:", validation.file_type)
    if validation.errors:
        print("Errors:", validation.errors)
    if validation.warnings:
        print("Warnings:", validation.warnings)

    if not validation.ok:
        raise SystemExit("Validation failed; parsing aborted.")

    parsed = fp.parse_file(file_path.name, content, strict=args.strict)
    print("Parse complete:")
    print("  file_type:", parsed.get("file_type"))
    print("  record_count:", parsed.get("record_count"))
    print("  transactions:", len(parsed.get("transactions", [])))
    print("  revenue_items:", len(parsed.get("revenue", [])))
    print("  cogs_items:", len(parsed.get("cogs_items", [])))
    print("  ga_expenses:", len(parsed.get("ga_expenses", [])))
    print("  trial_balance_items:", len(parsed.get("trial_balance_items", [])))
    print("  balance_sheet_items:", len(parsed.get("balance_sheet_items", [])))


if __name__ == "__main__":
    asyncio.run(main())
