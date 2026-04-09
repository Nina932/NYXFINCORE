import sys, json, os
from types import SimpleNamespace

DATASET_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None
DB = 'finai.db'
if not DATASET_ID:
    print(json.dumps({'error':'dataset_id_required'}))
    sys.exit(1)
if not os.path.exists(DB):
    print(json.dumps({'error':'db_missing','db':DB}))
    sys.exit(1)

import sqlite3
import sys
import os
# Ensure project root is on sys.path so 'app' package imports work
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('select id,name,upload_path,period from datasets where id=?', (DATASET_ID,))
ds = cur.fetchone()
if not ds:
    print(json.dumps({'error':'dataset_not_found','dataset_id':DATASET_ID}))
    sys.exit(1)

ds_id, ds_name, upload_path, period = ds
out = {'dataset_id': ds_id, 'dataset_name': ds_name, 'period': period}

# Re-parse uploaded file if available
parsed_raw = []
if upload_path and os.path.exists(upload_path):
    try:
        with open(upload_path, 'rb') as f:
            content = f.read()
        from app.services.file_parser import parse_file
        pf = parse_file(os.path.basename(upload_path), content)
        parsed_raw = pf.get('balance_sheet_items', [])
        out['parsed_raw_count'] = len(parsed_raw)
    except Exception as e:
        out['parsed_raw_error'] = str(e)
else:
    out['parsed_raw_error'] = 'upload_path_missing'

# Load persisted balance_sheet_items from DB
cur.execute('PRAGMA case_sensitive_like = OFF')
cur.execute('select account_code,account_name,ifrs_line_item,ifrs_statement,baku_bs_mapping,intercompany_entity,opening_balance,turnover_debit,turnover_credit,closing_balance,row_type from balance_sheet_items where dataset_id=?', (DATASET_ID,))
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
persisted = []
for r in rows:
    obj = SimpleNamespace(**{k:v for k,v in zip(cols,r)})
    persisted.append(obj)
out['persisted_count'] = len(persisted)

# Try to import aggregation function
try:
    from app.routers.analytics import _build_bs_from_parsed_items
    agg = _build_bs_from_parsed_items(persisted, period or '')
    out['aggregated'] = agg
    out['aggregated_lines'] = len(agg.get('rows',[])) if isinstance(agg, dict) else 0
except Exception as e:
    out['aggregated_error'] = str(e)

# Basic diffs
parsed_lines = set([r.get('ifrs_line_item') for r in parsed_raw if r.get('ifrs_line_item')]) if parsed_raw else set()
persisted_lines = set([getattr(p,'ifrs_line_item') for p in persisted if getattr(p,'ifrs_line_item',None)])
out['missing_in_persisted'] = sorted(list(parsed_lines - persisted_lines))[:50]
out['extra_in_persisted'] = sorted(list(persisted_lines - parsed_lines))[:50]

print(json.dumps(out, indent=2, default=str))
