"""
Company Ontology — domain-specific knowledge injected into every reasoning call.

This is NOT a generic prompt. It encodes real accounting rules, industry norms,
and company-specific behavior that the LLM must respect.
"""

from typing import Dict, Optional


# ─── Company Profiles ───

PROFILES: Dict[str, str] = {
    "NYX": """
Company: NYX Core Thinker LLC — fuel distribution & wholesale operator (Georgia).

CRITICAL ACCOUNTING RULES:
- COGS must come ONLY from P&L account 7110 (Cost of Goods Sold). NEVER use 1610 turnovers.
- Revenue recognized per IFRS 15 five-step model.
- Inventory valued using weighted average cost method.
- Revenue has two channels: Wholesale (23xxx accounts) and Retail (88xxx accounts).
- Georgian Lari (₾/GEL) is the reporting currency.

INDUSTRY CHARACTERISTICS:
- High-volume, low-margin business. Gross margin typically 8-15%.
- COGS/Revenue ratio normally 85-92%. Above 92% is a red flag.
- Working capital intensive — inventory turnover is critical.
- Exposed to: oil price volatility, GEL/USD forex, supplier concentration.
- Seasonal patterns: fuel demand peaks in summer (transport) and winter (heating).

FINANCIAL NORMS (fuel distribution):
- Gross margin: 8-15% (healthy), <8% (stressed), >15% (unusual — verify pricing)
- Net margin: 2-6% (normal), <0% (loss-making — investigate)
- D/E ratio: 1.0-2.5x (normal for fuel dist), >3x (over-leveraged)
- Current ratio: >1.0 required, <0.8 is liquidity crisis
- EBITDA margin: 3-8% (normal)

PERIOD DETECTION:
- Filenames often contain Georgian months: იანვარი=January, თებერვალი=February, etc.
- Russian: Январь, Февраль, Март, etc.
- Format: "Report- January 2026.xlsx" or "January 2026 (1).xlsx"

1C CHART OF ACCOUNTS:
- 4-digit codes (1110, 6110, 7110, 7310) are Georgian IFRS accounts
- 2-digit codes (01-99) are Russian 1C plan accounts
- Account 7110 = Cost of Goods Sold (COGS) — THE primary cost account
- Account 6110 = Revenue from sales
- Account 1110 = Fixed assets
""",

    "DEFAULT": """
Company: General commercial enterprise.

ACCOUNTING RULES:
- Follow IFRS standards for revenue recognition (IFRS 15) and asset impairment (IAS 36).
- COGS should match the P&L mapping sheet, not raw turnovers.
- Balance sheet must satisfy: Assets = Liabilities + Equity.

FINANCIAL NORMS:
- Gross margin varies by industry (20-60% for services, 5-20% for distribution)
- Current ratio > 1.0 is minimum for healthy liquidity
- D/E ratio > 3.0 is high leverage for most industries
""",
}


def get_company_context(company: str = "", period: str = "") -> str:
    """
    Return domain-specific context for the given company.
    This gets prepended to every LLM prompt in reasoning/debate.
    """
    company_upper = (company or "").upper()

    # Match known companies
    if "NYX" in company_upper or "SGP" in company_upper:
        profile = PROFILES["NYX"]
    else:
        profile = PROFILES["DEFAULT"]

    context = profile.strip()
    if period:
        context += f"\n\nCurrent analysis period: {period}"

    return context


def get_accounting_rules(company: str = "") -> Dict[str, str]:
    """Return structured accounting rules for validation."""
    company_upper = (company or "").upper()

    if "NYX" in company_upper:
        return {
            "cogs_account": "7110",
            "cogs_rule": "COGS must come from account 7110 only, not 1610 turnovers",
            "revenue_standard": "IFRS 15",
            "inventory_method": "Weighted average cost",
            "currency": "GEL (₾)",
            "industry": "fuel_distribution",
            "gross_margin_range": "8-15%",
            "net_margin_range": "2-6%",
        }

    return {
        "cogs_account": "varies",
        "revenue_standard": "IFRS 15",
        "currency": "varies",
        "industry": "general",
    }
