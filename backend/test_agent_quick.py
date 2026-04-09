# -*- coding: utf-8 -*-
"""Quick 3-question re-test with corrected expected values."""
import sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8080"

def ask(q):
    try:
        r = requests.post(f"{BASE}/api/agent/chat", json={"message":q,"history":[]}, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"response": f"ERROR: {e}", "tool_calls": []}

def val_in(val, resp):
    for fmt in [f"{val:,.2f}", f"{val:.2f}", f"{val:,.0f}"]:
        if fmt in resp: return True
    a = abs(val)
    if a >= 1e6:
        for d in [3,2,1,0]:
            if f"{a/1e6:.{d}f}" in resp: return True
    if a >= 1e3:
        for d in [1,0]:
            if f"{a/1e3:.{d}f}" in resp: return True
    return False

def test(num, question, values):
    print(f"\n  Q{num}: {question[:70]}...")
    result = ask(question)
    resp = result.get("response","")
    hits = 0
    total = len(values)
    for label, v in values.items():
        if val_in(v, resp):
            hits += 1
            print(f"    [HIT]  {label}: {v:,.2f}")
        else:
            print(f"    [MISS] {label}: {v:,.2f}")
    pct = hits/total*100 if total else 100
    status = "PASS" if pct >= 70 else "PARTIAL" if pct >= 40 else "FAIL"
    print(f"    Score: {hits}/{total} ({pct:.0f}%) [{status}]")
    return pct

def main():
    print("  QUICK RE-TEST (corrected expected values)")

    scores = []

    s = test(7, "Calculate Revenue Wholesale Diesel with product breakdown",
        {"Rev W Diesel": 13483316.04, "Diesel sabitumtso": 11970220.22, "Euro Diesel": 1513095.82})
    scores.append(("Q7", s))
    time.sleep(20)

    s = test(10, "Show Total Revenue = Wholesale + Retail + Other with each component value",
        {"Total Rev": 113136012.18, "Wholesale": 23332268.85, "Retail": 88141965.44, "Other": 1661777.89})
    scores.append(("Q10", s))
    time.sleep(20)

    s = test(17, "List all 5 G&A account codes with amounts and total G&A",
        {"GA Total": 6152227.55})
    scores.append(("Q17", s))

    print("\n  SUMMARY:")
    for q, s in scores:
        print(f"    {q}: {s:.0f}% {'PASS' if s >= 70 else 'PARTIAL' if s >= 40 else 'FAIL'}")
    avg = sum(s for _, s in scores) / len(scores)
    print(f"    Average: {avg:.0f}%")

if __name__ == "__main__":
    main()
