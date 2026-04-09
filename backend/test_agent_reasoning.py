# -*- coding: utf-8 -*-
"""
Test the FinAI Agent's reasoning on IS-CONSTRUCT questions.
Sends questions to the agent chat endpoint and evaluates responses.
"""
import sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8080"
PAUSE_SECONDS = 20

def ask_agent(question, history=None):
    """Send a question to the FinAI Agent and return its response."""
    payload = {"message": question, "history": history or []}
    try:
        r = requests.post(f"{BASE}/api/agent/chat", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        return {"response": f"ERROR: {e}", "tool_calls": []}

def value_in_response(val, response):
    """Check if a numeric value appears in the response in any common format."""
    # Exact formats
    val_str = f"{val:,.2f}"
    val_str_no_comma = f"{val:.2f}"
    val_str_round = f"{val:,.0f}"
    if val_str in response or val_str_no_comma in response or val_str_round in response:
        return True
    # Abbreviated format: 12,438,033.28 -> "12.438M" or "12.438"
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
    # Try with negative sign
    if val < 0:
        for decimals in [3, 2, 1, 0]:
            if abs_val >= 1_000_000:
                neg_str = f"-{abs_val/1_000_000:.{decimals}f}"
                if neg_str in response:
                    return True
    # Try smaller rounded variants
    val_round_1k = round(abs_val / 1000) * 1000
    if f"{val_round_1k:,.0f}" in response:
        return True
    # Check for value with different precision
    for precision in [0, 1, 2]:
        rounded = round(abs_val, precision)
        if f"{rounded:,.{precision}f}" in response:
            return True
    return False

def test_question(num, question, expected_keywords, expected_values=None):
    """Test a single question and grade the response."""
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

    # Check for expected keywords
    response_lower = response.lower()
    found = []
    missing = []
    for kw in expected_keywords:
        if kw.lower() in response_lower:
            found.append(kw)
        else:
            missing.append(kw)

    # Check for expected numeric values (with flexible matching)
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
    print("  FinAI AGENT REASONING TEST")
    print("  Sending IS-CONSTRUCT questions to the Agent via /api/agent/chat")
    print(f"  Pause between questions: {PAUSE_SECONDS}s")
    print("=" * 90)

    # Check agent status first
    try:
        status = requests.get(f"{BASE}/api/agent/status").json()
        print(f"\n  Agent status: {status.get('status', '?')}")
        print(f"  API key: {status.get('api_key', '?')}")
        if status.get('api_key') != 'configured':
            print("\n  WARNING: Anthropic API key not configured! Agent won't work.")
            print("  Set ANTHROPIC_API_KEY in .env file")
            return 1
    except Exception as e:
        print(f"\n  ERROR checking status: {e}")
        return 1

    scores = []

    # ── Q1: Classification trap question ──
    s = test_question(
        1,
        "A trainee argues that 'ბუნებრივი აირი (საბითუმო), მ3' should be classified under Revenue Wholesale CNG because it says 'საბითუმო' (wholesale). Is the trainee correct? Which P&L line does this product belong to?",
        ["retail", "cng", "incorrect"],
        {"CNG Revenue": 12438033.28}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q5: G&A filtering ──
    s = test_question(
        5,
        "The Base sheet contains Account Dr code '7310.02.1'. A colleague also finds '7310.01.1' and wants to include it in G&A expenses. Should '7310.01.1' be included in G&A? List the exact 5 account codes that are included.",
        ["7310.02.1", "7410", "7410.01", "8220.01.1", "9210", "no"],
        {"GA Total": 6152227.55}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q6: Revenue calculation ──
    s = test_question(
        6,
        "Calculate Revenue Wholesale Petrol (Lari). Which 3 products does it include? Show each product's Net Revenue and the total.",
        ["ევრო რეგულარი", "პრემიუმი", "სუპერი", "wholesale", "petrol"],
        {"Rev W Petrol": 7671389.84, "Euro Regular Import": 5583855.32, "Premium Re-export": 1828750.59, "Super Re-export": 258783.93}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q15: Negative margin analysis ──
    s = test_question(
        15,
        "Calculate Gross Margin Wholesale Petrol. Is this margin positive or negative? What does this imply about the business model?",
        ["negative", "wholesale", "petrol", "retail"],
        {"GM W Petrol": -2314691.98, "Rev W Petrol": 7671389.84}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q18: EBITDA ──
    s = test_question(
        18,
        "Calculate EBITDA and the EBITDA margin percentage. Show the formula: Total Gross Profit minus G&A Expenses.",
        ["ebitda", "gross profit", "g&a", "4.42"],
        {"EBITDA": 5001607.20, "TGP": 11153834.75, "GA": 6152227.55}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q19: Error detection ──
    s = test_question(
        19,
        "A finance analyst reports Revenue Retail LPG = 441,817.61. Is this value correct? If not, what is the error and what is the correct value?",
        ["incorrect", "gross", "net", "vat", "374"],
        {"Correct LPG": 374421.39, "Gross LPG": 441817.61}
    )
    scores.append(s)
    print(f"\n  Pausing {PAUSE_SECONDS}s...")
    time.sleep(PAUSE_SECONDS)

    # ── Q20: Total Revenue trap ──
    s = test_question(
        20,
        "A manager says Total Revenue should be 131,671,728.21 from the Итог row of Revenue Breakdown. Is this correct? What is the correct Total Revenue and which column should be used?",
        ["net", "vat", "gross", "column d"],
        {"Correct Revenue": 113136012.18}
    )
    scores.append(s)

    # ── SUMMARY ──
    print("\n\n" + "=" * 90)
    print("  AGENT REASONING TEST — SUMMARY")
    print("=" * 90)
    qnums = [1, 5, 6, 15, 18, 19, 20]
    for i, s in enumerate(scores):
        status = "PASS" if s >= 70 else "PARTIAL" if s >= 40 else "FAIL"
        icon = "✓" if s >= 70 else "⚠" if s >= 40 else "✗"
        print(f"  {icon} Q{qnums[i]:2d}: {s:.0f}% [{status}]")
    avg = sum(scores) / len(scores) if scores else 0
    print(f"\n  Average Score: {avg:.0f}%")
    if avg >= 80:
        print("  VERDICT: Agent demonstrates strong financial reasoning ✓")
    elif avg >= 60:
        print("  VERDICT: Agent demonstrates good financial reasoning with minor gaps")
    elif avg >= 40:
        print("  VERDICT: Agent shows partial understanding — needs improvement")
    else:
        print("  VERDICT: Agent needs significant improvement in financial intelligence")
    print("=" * 90)

    return 0

if __name__ == "__main__":
    sys.exit(main())
