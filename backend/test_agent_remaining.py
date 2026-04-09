# -*- coding: utf-8 -*-
"""
Test remaining IS-CONSTRUCT questions (Q2-Q4, Q7-Q14, Q16-Q17) via FinAI Agent.
Questions Q1, Q5, Q6, Q15, Q18, Q19, Q20 already tested (98% pass).
"""
import sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8080"
PAUSE_SECONDS = 20

def ask_agent(question, history=None):
    payload = {"message": question, "history": history or []}
    try:
        r = requests.post(f"{BASE}/api/agent/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"response": f"ERROR: {e}", "tool_calls": []}

def value_in_response(val, response):
    val_str = f"{val:,.2f}"
    val_str_no_comma = f"{val:.2f}"
    val_str_round = f"{val:,.0f}"
    if val_str in response or val_str_no_comma in response or val_str_round in response:
        return True
    abs_val = abs(val)
    if abs_val >= 1_000_000:
        for decimals in [3, 2, 1, 0]:
            abbr = f"{abs_val/1_000_000:.{decimals}f}"
            if abbr in response:
                return True
    elif abs_val >= 1_000:
        for decimals in [1, 0]:
            abbr = f"{abs_val/1_000:.{decimals}f}"
            if abbr in response:
                return True
    if val < 0:
        for decimals in [3, 2, 1, 0]:
            if abs_val >= 1_000_000:
                neg_str = f"-{abs_val/1_000_000:.{decimals}f}"
                if neg_str in response:
                    return True
    val_round_1k = round(abs_val / 1000) * 1000
    if f"{val_round_1k:,.0f}" in response:
        return True
    for precision in [0, 1, 2]:
        rounded = round(abs_val, precision)
        if f"{rounded:,.{precision}f}" in response:
            return True
    return False

def test_question(num, question, expected_keywords, expected_values=None):
    print(f"\n{'='*90}")
    print(f"  Q{num}: {question[:80]}...")
    print(f"{'='*90}")

    result = ask_agent(question)
    response = result.get("response", "")
    tools_used = [tc.get("tool", "?") for tc in result.get("tool_calls", [])]

    print(f"\n  Tools used: {tools_used if tools_used else 'none'}")
    print(f"\n  AGENT RESPONSE:")
    for line in response.split('\n'):
        print(f"    {line}")

    response_lower = response.lower()
    found = []
    missing = []
    for kw in expected_keywords:
        if kw.lower() in response_lower:
            found.append(kw)
        else:
            missing.append(kw)

    value_hits = 0
    value_total = 0
    if expected_values:
        for label, val in expected_values.items():
            value_total += 1
            if value_in_response(val, response):
                value_hits += 1
            else:
                print(f"    [MISS] Expected value for '{label}': {val:,.2f}")

    kw_score = len(found) / len(expected_keywords) * 100 if expected_keywords else 100
    val_score = value_hits / value_total * 100 if value_total else 100
    overall = (kw_score + val_score) / 2

    print(f"\n  GRADE:")
    print(f"    Keywords: {len(found)}/{len(expected_keywords)} ({kw_score:.0f}%)")
    if missing:
        print(f"    Missing: {missing}")
    if value_total:
        print(f"    Values:   {value_hits}/{value_total} ({val_score:.0f}%)")
    print(f"    Overall:  {overall:.0f}%")

    return overall

def main():
    print("=" * 90)
    print("  FinAI AGENT — REMAINING IS-CONSTRUCT QUESTIONS TEST")
    print("  Testing Q2-Q4, Q7-Q14, Q16-Q17 via /api/agent/chat")
    print(f"  Pause between questions: {PAUSE_SECONDS}s")
    print("=" * 90)

    try:
        status = requests.get(f"{BASE}/api/agent/status").json()
        print(f"\n  Agent status: {status.get('status', '?')}")
        if status.get('api_key') != 'configured':
            print("  WARNING: API key not configured!")
            return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    scores = []
    qnums = []

    # ── Q2: COGS discrepancy ──
    s = test_question(
        2,
        "In the COGS Breakdown sheet, there is a product 'ევრო რეგულარი (საბითუმო)'. Under which COGS line does this product belong? This product does NOT appear in Revenue Breakdown — is this a discrepancy or expected behavior?",
        ["cogs", "wholesale", "petrol", "accounting", "revenue"],
        {"COGS W Petrol total": 9986081.82}
    )
    scores.append(s); qnums.append(2)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q3: COGS columns ──
    s = test_question(
        3,
        "Besides Column K (Account code 6), which two additional columns contribute to total COGS per product? What Account codes do they use? What is the risk of omitting them?",
        ["7310", "8230", "column l", "column o"],
        {}
    )
    scores.append(s); qnums.append(3)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q4: New product classification ──
    s = test_question(
        4,
        "Suppose a new product appears in the data: 'კეროსინი (საბითუმო), კგ'. Under which Revenue line and COGS line should it be classified? What structural change does this require in the IS?",
        ["wholesale", "kerosene", "new"],
        {}
    )
    scores.append(s); qnums.append(4)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q7: Revenue Wholesale Diesel ──
    s = test_question(
        7,
        "Calculate Revenue Wholesale Diesel. This category has 2 products with different physical units (litres vs kg). Does the unit difference affect Net Revenue aggregation? Show each product's Net Revenue.",
        ["diesel", "wholesale", "unit"],
        {"Rev W Diesel": 13483316.04}
    )
    scores.append(s); qnums.append(7)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q8: Total Wholesale Revenue ──
    s = test_question(
        8,
        "Calculate Total Wholesale Revenue = Petrol + Diesel + Bitumen. Show each sub-component.",
        ["petrol", "diesel", "bitumen", "wholesale"],
        {"Rev W total": 23332268.85, "Rev W Petrol": 7671389.84, "Rev W Diesel": 13483316.04, "Rev W Bitumen": 2177562.97}
    )
    scores.append(s); qnums.append(8)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q9: Revenue Retail CNG % ──
    s = test_question(
        9,
        "Calculate Revenue Retail CNG and express it as a percentage of Total Revenue. How many products contribute to this line?",
        ["cng", "retail", "%"],
        {"Rev R CNG": 12438033.28, "Total Revenue": 113136012.18}
    )
    scores.append(s); qnums.append(9)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q10: Other Revenue + Total Revenue ──
    s = test_question(
        10,
        "What is Other Revenue? Show the Total Revenue formula: Revenue = Wholesale + Retail + Other. Verify that all components sum to Total Revenue.",
        ["other", "wholesale", "retail", "total"],
        {"Other Revenue": 1661777.89, "Total Revenue": 113136012.18, "Rev Wholesale": 23332268.85, "Rev Retail": 88141965.44}
    )
    scores.append(s); qnums.append(10)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q11: COGS Wholesale Petrol products ──
    s = test_question(
        11,
        "List all products under COGS Wholesale Petrol. For each product show the 3-column COGS breakdown (Col K/L/O) and total. How many products are there?",
        ["cogs", "wholesale", "petrol"],
        {"COGS W Petrol": 9986081.82}
    )
    scores.append(s); qnums.append(11)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q12: Specific COGS product ──
    s = test_question(
        12,
        "What is the COGS for product 'დიზელი (საბითუმო)'? Show each column individually: Col K (account 6), Col L (account 7310), Col O (account 8230), and the total.",
        ["დიზელი", "7310", "8230", "6"],
        {}
    )
    scores.append(s); qnums.append(12)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q13: Total COGS Retail ──
    s = test_question(
        13,
        "Calculate Total COGS Retail with all 4 sub-components: Petrol, Diesel, CNG, LPG. Show each value.",
        ["cogs", "retail", "petrol", "diesel", "cng", "lpg"],
        {"COGS Retail total": 76561964.08}
    )
    scores.append(s); qnums.append(13)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q14: Zero-COGS products ──
    s = test_question(
        14,
        "Are there any products with zero COGS in the current period? Should they still be included in the P&L? What does a non-zero opening balance (Нач. сальдо деб.) imply for such products?",
        ["zero", "included", "inventory", "balance"],
        {}
    )
    scores.append(s); qnums.append(14)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q16: Total Gross Profit formula ──
    s = test_question(
        16,
        "Calculate Total Gross Profit using the formula: GM Wholesale + GM Retail + Other Revenue - Other COGS. Show each component.",
        ["gross profit", "wholesale", "retail", "other"],
        {"TGP": 11153834.75, "GM Wholesale": -2084604.58, "GM Retail": 11580001.36}
    )
    scores.append(s); qnums.append(16)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q17: G&A 5 account codes ──
    s = test_question(
        17,
        "List all G&A expense accounts from the Base sheet with their amounts. Show the 5 Account Dr codes and their individual amounts, plus the total G&A.",
        ["7310.02.1", "7410", "7410.01", "8220.01.1", "9210"],
        {"GA Total": 6152227.55}
    )
    scores.append(s); qnums.append(17)

    # ── SUMMARY ──
    print("\n\n" + "=" * 90)
    print("  REMAINING IS-CONSTRUCT TEST — SUMMARY")
    print("=" * 90)
    for i, s in enumerate(scores):
        status = "PASS" if s >= 70 else "PARTIAL" if s >= 40 else "FAIL"
        icon = "✓" if s >= 70 else "⚠" if s >= 40 else "✗"
        print(f"  {icon} Q{qnums[i]:2d}: {s:.0f}% [{status}]")
    avg = sum(scores) / len(scores) if scores else 0
    print(f"\n  Average Score: {avg:.0f}%")
    if avg >= 80:
        print("  VERDICT: Agent demonstrates strong financial reasoning ✓")
    elif avg >= 60:
        print("  VERDICT: Good reasoning with minor gaps")
    elif avg >= 40:
        print("  VERDICT: Partial understanding — needs improvement")
    else:
        print("  VERDICT: Significant improvement needed")
    print("=" * 90)

    return 0

if __name__ == "__main__":
    sys.exit(main())
