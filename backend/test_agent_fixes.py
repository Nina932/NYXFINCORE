# -*- coding: utf-8 -*-
"""Quick re-test of Q7, Q10, Q17 that failed/partially passed."""
import sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8080"
PAUSE = 20

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

def test(num, question, keywords, values=None):
    print(f"\n{'='*80}")
    print(f"  Q{num}: {question[:75]}...")
    print(f"{'='*80}")
    result = ask(question)
    resp = result.get("response","")
    tools = [tc.get("tool","?") for tc in result.get("tool_calls",[])]
    print(f"  Tools: {tools}")
    print(f"  Response ({len(resp)} chars):")
    for l in resp.split('\n')[:25]:
        print(f"    {l}")
    if len(resp.split('\n')) > 25:
        print(f"    ... ({len(resp.split(chr(10)))-25} more lines)")

    rl = resp.lower()
    kw_found = sum(1 for k in keywords if k.lower() in rl)
    kw_total = len(keywords)
    kw_missing = [k for k in keywords if k.lower() not in rl]

    val_found = 0
    val_total = 0
    if values:
        for label, v in values.items():
            val_total += 1
            if val_in(v, resp):
                val_found += 1
                print(f"  [HIT]  {label}: {v:,.2f}")
            else:
                print(f"  [MISS] {label}: {v:,.2f}")

    kw_pct = kw_found/kw_total*100 if kw_total else 100
    val_pct = val_found/val_total*100 if val_total else 100
    score = (kw_pct + val_pct) / 2

    print(f"\n  Keywords: {kw_found}/{kw_total} ({kw_pct:.0f}%)")
    if kw_missing: print(f"  Missing: {kw_missing}")
    if val_total: print(f"  Values: {val_found}/{val_total} ({val_pct:.0f}%)")
    print(f"  SCORE: {score:.0f}% {'PASS' if score >= 70 else 'PARTIAL' if score >= 40 else 'FAIL'}")
    return score

def main():
    print("=" * 80)
    print("  RE-TEST: Q7, Q10, Q17 (after dataset filter fix)")
    print("=" * 80)

    try:
        s = requests.get(f"{BASE}/api/agent/status").json()
        print(f"  Agent: {s.get('status')}, API: {s.get('api_key')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    scores = []

    s = test(7,
        "Calculate Revenue Wholesale Diesel. This category has 2 products with different physical units (litres vs kg). Does the unit difference affect Net Revenue aggregation? Show each product's Net Revenue.",
        ["diesel", "wholesale", "unit", "lari"],
        {"Rev W Diesel": 59652107.77}
    )
    scores.append(("Q7", s))
    time.sleep(PAUSE)

    s = test(10,
        "What is Other Revenue? Show the Total Revenue formula: Revenue = Wholesale + Retail + Other. Verify that all components sum to Total Revenue.",
        ["other", "wholesale", "retail", "total"],
        {"Other Revenue": 938274.22, "Total Revenue": 113136012.18, "Rev Wholesale": 69497618.20, "Rev Retail": 42700119.76}
    )
    scores.append(("Q10", s))
    time.sleep(PAUSE)

    s = test(17,
        "List all G&A expense accounts from the Base sheet with their amounts. Show the 5 Account Dr codes and their individual amounts, plus the total G&A.",
        ["7310.02.1", "7410", "7410.01", "8220.01.1", "9210"],
        {"GA Total": 6152227.55}
    )
    scores.append(("Q17", s))

    print("\n\n" + "=" * 80)
    print("  RE-TEST SUMMARY")
    print("=" * 80)
    for q, s in scores:
        status = "PASS" if s >= 70 else "PARTIAL" if s >= 40 else "FAIL"
        icon = "✓" if s >= 70 else "⚠" if s >= 40 else "✗"
        print(f"  {icon} {q}: {s:.0f}% [{status}]")
    avg = sum(s for _, s in scores) / len(scores)
    print(f"\n  Average: {avg:.0f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
