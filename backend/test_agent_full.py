# -*- coding: utf-8 -*-
"""Quick test: send 3 critical questions to agent and print FULL responses."""
import sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8')
BASE = "http://localhost:8080"

def ask(q):
    r = requests.post(f"{BASE}/api/agent/chat", json={"message": q, "history": []}, timeout=120)
    return r.json()

# Q19 — The critical Gross vs Net trap
print("=" * 90)
print("Q19: Gross vs Net Revenue LPG")
print("=" * 90)
d = ask("A finance analyst reports Revenue Retail LPG = 441,817.61 GEL. Is this value correct? If not, what is the error and what is the correct value? Check the actual data.")
print("TOOLS:", [t.get("tool") for t in d.get("tool_calls", [])])
print("\nFULL RESPONSE:")
print(d.get("response", "NO RESPONSE"))

time.sleep(3)

# Q5 — Strict G&A filter
print("\n\n" + "=" * 90)
print("Q5: G&A Account Code Filter")
print("=" * 90)
d = ask("Our G&A expenses use exactly 5 Account Dr codes: 7310.02.1, 7410, 7410.01, 8220.01.1, 9210. A colleague found account '7310.01.1' in the Base sheet and wants to add it to G&A. Should 7310.01.1 be included? Think carefully — this is a strict exact-match filter, not a prefix match.")
print("TOOLS:", [t.get("tool") for t in d.get("tool_calls", [])])
print("\nFULL RESPONSE:")
print(d.get("response", "NO RESPONSE"))

time.sleep(3)

# Q1 — Classification trap
print("\n\n" + "=" * 90)
print("Q1: CNG Classification Trap")
print("=" * 90)
d = ask("A trainee argues that 'ბუნებრივი აირი (საბითუმო), მ3' should be classified under Revenue Wholesale CNG because 'საბითუმო' means wholesale. Is the trainee correct? Check the actual product mapping in our data — which P&L line does this product belong to and why?")
print("TOOLS:", [t.get("tool") for t in d.get("tool_calls", [])])
print("\nFULL RESPONSE:")
print(d.get("response", "NO RESPONSE"))
