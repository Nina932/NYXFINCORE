"""
Verify all three fixes:
1. admin_expenses no longer 0 in SQLite
2. Warehouse has time series data
3. Period aggregation endpoints work

Run: python verify_fixes.py
"""
import sqlite3
import os
import requests

BASE = 'http://127.0.0.1:9200'
STORE_DB = 'data/finai_store.db'


def verify_admin_expenses():
    """Task 1: Verify admin_expenses is no longer 0."""
    print("=" * 60)
    print("TASK 1: Verify admin_expenses fix")
    print("=" * 60)
    if not os.path.exists(STORE_DB):
        print("  ERROR: finai_store.db not found")
        return False

    conn = sqlite3.connect(STORE_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT fp.period_name, fs.value
        FROM financial_snapshots fs
        JOIN financial_periods fp ON fs.period_id = fp.id
        WHERE fs.field_name = 'admin_expenses'
        ORDER BY fp.period_name
    """).fetchall()
    conn.close()

    all_ok = True
    for r in rows:
        val = r["value"]
        status = "OK" if val != 0 else "STILL ZERO"
        if val == 0:
            all_ok = False
        print(f"  {r['period_name']}: admin_expenses = {val:,.0f}  [{status}]")

    if not rows:
        print("  WARNING: No admin_expenses records found")
        return False
    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def verify_warehouse():
    """Task 2: Verify warehouse has time series data."""
    print("\n" + "=" * 60)
    print("TASK 2: Verify warehouse time series")
    print("=" * 60)
    try:
        r = requests.get(f'{BASE}/api/agent/agents/warehouse/status', timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f"  Warehouse status: {d}")
    except Exception as e:
        print(f"  Warehouse status endpoint: {e}")

    # Trigger sync
    try:
        r = requests.post(f'{BASE}/api/agent/agents/warehouse/sync', timeout=30)
        if r.status_code == 200:
            d = r.json()
            print(f"  Sync result: {d}")
            snap_count = d.get("dw_financial_snapshots", 0)
            print(f"  Financial snapshots in warehouse: {snap_count}")
            return snap_count > 0
    except Exception as e:
        print(f"  Sync error: {e}")

    # Try direct Python check
    try:
        import sys
        sys.path.insert(0, '.')
        from app.services.warehouse import warehouse
        if not warehouse._initialized:
            warehouse.initialize()
        counts = warehouse.sync_from_sqlite()
        print(f"  Direct sync counts: {counts}")
        return counts.get("dw_financial_snapshots", 0) > 0
    except Exception as e:
        print(f"  Direct sync error: {e}")
        return False


def verify_period_aggregation():
    """Task 3: Verify period aggregation endpoints."""
    print("\n" + "=" * 60)
    print("TASK 3: Verify period aggregation endpoints")
    print("=" * 60)
    endpoints = [
        ("/api/agent/agents/periods/quarterly?year=2025", "Quarterly"),
        ("/api/agent/agents/periods/ytd?year=2025&month=12", "YTD"),
        ("/api/agent/agents/periods/annual?year=2025", "Annual"),
        ("/api/agent/agents/periods/summary?company_id=1", "Summary"),
    ]
    all_ok = True
    for path, label in endpoints:
        try:
            r = requests.get(f'{BASE}{path}', timeout=10)
            if r.status_code == 200:
                d = r.json()
                # Check if there's meaningful data
                has_data = bool(d.get("quarters") or d.get("financials") or d.get("aggregations"))
                print(f"  {label}: OK (status=200, has_data={has_data})")
            else:
                print(f"  {label}: HTTP {r.status_code}")
                all_ok = False
        except Exception as e:
            print(f"  {label}: ERROR {e}")
            all_ok = False

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("\nFinAI OS — Data Fix Verification\n")
    t1 = verify_admin_expenses()
    t2 = verify_warehouse()
    t3 = verify_period_aggregation()
    print("\n" + "=" * 60)
    print(f"OVERALL: Task1={'PASS' if t1 else 'FAIL'}  Task2={'PASS' if t2 else 'FAIL'}  Task3={'PASS' if t3 else 'FAIL'}")
    print("=" * 60)
