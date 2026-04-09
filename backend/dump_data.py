import sys, json, requests
sys.stdout.reconfigure(encoding='utf-8')
BASE = "http://localhost:8080"

# Revenue
r = requests.get(f"{BASE}/api/analytics/revenue")
rev = r.json()
print("=== REVENUE PRODUCTS ===")
for p in rev.get("products", []):
    print(json.dumps(p, ensure_ascii=False))
print("\n=== REVENUE SEGMENTS ===")
print(json.dumps(rev.get("segments", {}), ensure_ascii=False, indent=2))
print("\n=== REVENUE BY CATEGORY ===")
print(json.dumps(rev.get("by_category", {}), ensure_ascii=False, indent=2))
print("\n=== REVENUE TOTALS ===")
print(json.dumps(rev.get("totals", {}), ensure_ascii=False, indent=2))

# COGS — query DB directly
print("\n\n=== COGS ITEMS (from DB) ===")
import sqlite3
conn = sqlite3.connect("finai.db")
c = conn.cursor()
c.execute("""SELECT product, col6_amount, col7310_amount, col8230_amount, total_cogs, segment, category
             FROM cogs_items WHERE dataset_id = (SELECT id FROM datasets WHERE is_active = 1 LIMIT 1)
             ORDER BY segment, category, product""")
for row in c.fetchall():
    print(json.dumps({"product": row[0], "col6": row[1], "col7310": row[2], "col8230": row[3],
                       "total_cogs": row[4], "segment": row[5], "category": row[6]}, ensure_ascii=False))

# G&A
print("\n\n=== G&A ITEMS (from DB) ===")
c.execute("""SELECT account_code, account_name, amount
             FROM ga_expense_items WHERE dataset_id = (SELECT id FROM datasets WHERE is_active = 1 LIMIT 1)
             ORDER BY account_code""")
for row in c.fetchall():
    print(json.dumps({"code": row[0], "name": row[1], "amount": row[2]}, ensure_ascii=False))

# Revenue items from DB for gross/vat/net detail
print("\n\n=== REVENUE ITEMS (from DB with gross/vat/net) ===")
c.execute("""SELECT product, gross, vat, net, segment, category
             FROM revenue_items WHERE dataset_id = (SELECT id FROM datasets WHERE is_active = 1 LIMIT 1)
             ORDER BY segment, category, product""")
for row in c.fetchall():
    print(json.dumps({"product": row[0], "gross": row[1], "vat": row[2], "net": row[3],
                       "segment": row[4], "category": row[5]}, ensure_ascii=False))

conn.close()
