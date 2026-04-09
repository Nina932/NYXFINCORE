#!/usr/bin/env python
"""Re-parse an uploaded dataset and upsert BalanceSheetItem records.
Usage: python scripts/reparse_and_upsert_bsi.py <dataset_id>
"""
import sys
import asyncio
import json
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import AsyncSessionLocal
from app.services.file_parser import parse_file
from app.models.all_models import Dataset, BalanceSheetItem
from sqlalchemy import select


async def main(dataset_id: int):
    async with AsyncSessionLocal() as db:
        # Load dataset
        ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
        if not ds:
            print(json.dumps({"error": "Dataset not found", "dataset_id": dataset_id}))
            return

        upload_path = ds.upload_path
        original_name = ds.original_filename or Path(upload_path).name
        if not upload_path or not Path(upload_path).exists():
            print(json.dumps({"error": "Upload file not found on disk", "upload_path": upload_path}))
            return

        # Reparse file
        with open(upload_path, 'rb') as f:
            content = f.read()

        parsed = parse_file(original_name, content)
        parsed_bsi = parsed.get('balance_sheet_items', [])

        inserted = 0
        updated = 0
        for pb in parsed_bsi:
            # only consider items with an IFRS line (we want to persist P&L with IFRS lines)
            if not pb.get('ifrs_line_item'):
                continue

            # find existing record by dataset + account_code + ifrs_line_item
            q = select(BalanceSheetItem).where(
                BalanceSheetItem.dataset_id == dataset_id,
                BalanceSheetItem.account_code == (pb.get('account_code') or ''),
                BalanceSheetItem.ifrs_line_item == (pb.get('ifrs_line_item') or ''),
            )
            existing = (await db.execute(q)).scalars().first()
            if existing:
                # update fields
                existing.account_name = pb.get('account_name') or existing.account_name
                existing.ifrs_statement = pb.get('ifrs_statement') or existing.ifrs_statement
                existing.baku_bs_mapping = pb.get('baku_bs_mapping') or existing.baku_bs_mapping
                existing.intercompany_entity = pb.get('intercompany_entity') or existing.intercompany_entity
                existing.opening_balance = float(pb.get('opening_balance') or 0)
                existing.turnover_debit = float(pb.get('turnover_debit') or 0)
                existing.turnover_credit = float(pb.get('turnover_credit') or 0)
                existing.closing_balance = float(pb.get('closing_balance') or 0)
                existing.row_type = pb.get('row_type') or existing.row_type
                updated += 1
            else:
                db.add(BalanceSheetItem(
                    dataset_id=dataset_id,
                    account_code=pb.get('account_code') or '',
                    account_name=pb.get('account_name') or '',
                    ifrs_line_item=pb.get('ifrs_line_item') or '',
                    ifrs_statement=pb.get('ifrs_statement') or '',
                    baku_bs_mapping=pb.get('baku_bs_mapping') or '',
                    intercompany_entity=pb.get('intercompany_entity') or '',
                    opening_balance=float(pb.get('opening_balance') or 0),
                    turnover_debit=float(pb.get('turnover_debit') or 0),
                    turnover_credit=float(pb.get('turnover_credit') or 0),
                    closing_balance=float(pb.get('closing_balance') or 0),
                    row_type=pb.get('row_type') or '',
                    currency='GEL', period=ds.period or '',
                ))
                inserted += 1

        await db.commit()

        # Return summary
        print(json.dumps({
            "dataset_id": dataset_id,
            "dataset_name": ds.name,
            "parsed_bsi_count": len(parsed_bsi),
            "inserted": inserted,
            "updated": updated,
        }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/reparse_and_upsert_bsi.py <dataset_id>")
        sys.exit(1)
    ds_id = int(sys.argv[1])
    asyncio.run(main(ds_id))
