"""
Phase S-3: Georgian Localization (i18n)
=========================================
Bilingual translation system for financial terms.

Supports:
  - English (en) — default
  - Georgian (ka) — ქართული

60+ financial terms covering:
  - P&L line items
  - Balance sheet items
  - Financial ratios
  - Accounting concepts
  - Report labels
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# TRANSLATION DICTIONARY
# ═══════════════════════════════════════════════════════════════════

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ── P&L Line Items ──────────────────────────────────────────
    "revenue":              {"en": "Revenue",               "ka": "შემოსავალი"},
    "sales":                {"en": "Sales",                 "ka": "გაყიდვები"},
    "cogs":                 {"en": "Cost of Goods Sold",    "ka": "თვითღირებულება"},
    "cost_of_sales":        {"en": "Cost of Sales",         "ka": "გაყიდვების ღირებულება"},
    "gross_profit":         {"en": "Gross Profit",          "ka": "მთლიანი მოგება"},
    "ga_expenses":          {"en": "G&A Expenses",          "ka": "ადმინისტრაციული ხარჯები"},
    "operating_expenses":   {"en": "Operating Expenses",    "ka": "საოპერაციო ხარჯები"},
    "selling_expenses":     {"en": "Selling Expenses",      "ka": "გაყიდვის ხარჯები"},
    "ebitda":               {"en": "EBITDA",                "ka": "ებითდა"},
    "depreciation":         {"en": "Depreciation",          "ka": "ცვეთა"},
    "amortization":         {"en": "Amortization",          "ka": "ამორტიზაცია"},
    "finance_expense":      {"en": "Finance Expense",       "ka": "საფინანსო ხარჯი"},
    "interest_expense":     {"en": "Interest Expense",      "ka": "პროცენტის ხარჯი"},
    "tax_expense":          {"en": "Tax Expense",           "ka": "საგადასახადო ხარჯი"},
    "net_profit":           {"en": "Net Profit",            "ka": "წმინდა მოგება"},
    "net_income":           {"en": "Net Income",            "ka": "წმინდა შემოსავალი"},
    "other_income":         {"en": "Other Income",          "ka": "სხვა შემოსავალი"},

    # ── Balance Sheet ───────────────────────────────────────────
    "balance_sheet":        {"en": "Balance Sheet",         "ka": "ბალანსი"},
    "assets":               {"en": "Assets",                "ka": "აქტივები"},
    "total_assets":         {"en": "Total Assets",          "ka": "სულ აქტივები"},
    "current_assets":       {"en": "Current Assets",        "ka": "მიმდინარე აქტივები"},
    "non_current_assets":   {"en": "Non-Current Assets",    "ka": "გრძელვადიანი აქტივები"},
    "cash":                 {"en": "Cash",                  "ka": "ფულადი სახსრები"},
    "accounts_receivable":  {"en": "Accounts Receivable",   "ka": "მისაღები თანხები"},
    "inventory":            {"en": "Inventory",             "ka": "მარაგები"},
    "fixed_assets":         {"en": "Fixed Assets",          "ka": "ძირითადი საშუალებები"},
    "intangible_assets":    {"en": "Intangible Assets",     "ka": "არამატერიალური აქტივები"},
    "liabilities":          {"en": "Liabilities",           "ka": "ვალდებულებები"},
    "total_liabilities":    {"en": "Total Liabilities",     "ka": "სულ ვალდებულებები"},
    "current_liabilities":  {"en": "Current Liabilities",   "ka": "მიმდინარე ვალდებულებები"},
    "long_term_debt":       {"en": "Long-Term Debt",        "ka": "გრძელვადიანი ვალი"},
    "accounts_payable":     {"en": "Accounts Payable",      "ka": "გადასახდელი თანხები"},
    "equity":               {"en": "Equity",                "ka": "კაპიტალი"},
    "total_equity":         {"en": "Total Equity",          "ka": "სულ კაპიტალი"},
    "share_capital":        {"en": "Share Capital",         "ka": "საწესდებო კაპიტალი"},
    "retained_earnings":    {"en": "Retained Earnings",     "ka": "გაუნაწილებელი მოგება"},

    # ── Cash Flow ───────────────────────────────────────────────
    "cash_flow":            {"en": "Cash Flow",             "ka": "ფულადი ნაკადები"},
    "operating_cf":         {"en": "Operating Cash Flow",   "ka": "საოპერაციო ფულადი ნაკადი"},
    "investing_cf":         {"en": "Investing Cash Flow",   "ka": "საინვესტიციო ფულადი ნაკადი"},
    "financing_cf":         {"en": "Financing Cash Flow",   "ka": "საფინანსო ფულადი ნაკადი"},

    # ── Financial Ratios ────────────────────────────────────────
    "gross_margin":         {"en": "Gross Margin",          "ka": "მთლიანი მარჟა"},
    "net_margin":           {"en": "Net Margin",            "ka": "წმინდა მარჟა"},
    "ebitda_margin":        {"en": "EBITDA Margin",         "ka": "ებითდა მარჟა"},
    "current_ratio":        {"en": "Current Ratio",         "ka": "მიმდინარე კოეფიციენტი"},
    "quick_ratio":          {"en": "Quick Ratio",           "ka": "სწრაფი ლიკვიდობის კოეფიციენტი"},
    "debt_to_equity":       {"en": "Debt to Equity",        "ka": "ვალი კაპიტალთან"},
    "working_capital":      {"en": "Working Capital",       "ka": "საბრუნავი კაპიტალი"},
    "return_on_equity":     {"en": "Return on Equity",      "ka": "კაპიტალის უკუგება"},
    "return_on_assets":     {"en": "Return on Assets",      "ka": "აქტივების უკუგება"},
    "interest_coverage":    {"en": "Interest Coverage",     "ka": "პროცენტის დაფარვა"},
    "inventory_turnover":   {"en": "Inventory Turnover",    "ka": "მარაგის ბრუნვა"},
    "asset_turnover":       {"en": "Asset Turnover",        "ka": "აქტივების ბრუნვა"},
    "profit_margin":        {"en": "Profit Margin",         "ka": "მოგების მარჟა"},
    "operating_margin":     {"en": "Operating Margin",      "ka": "საოპერაციო მარჟა"},

    # ── Report Labels ───────────────────────────────────────────
    "income_statement":     {"en": "Income Statement",      "ka": "მოგება-ზარალის ანგარიშგება"},
    "financial_report":     {"en": "Financial Report",      "ka": "ფინანსური ანგარიშგება"},
    "executive_summary":    {"en": "Executive Summary",     "ka": "მოკლე მიმოხილვა"},
    "health_score":         {"en": "Health Score",          "ka": "ჯანმრთელობის ქულა"},
    "strategy":             {"en": "Strategy",              "ka": "სტრატეგია"},
    "recommendation":       {"en": "Recommendation",        "ka": "რეკომენდაცია"},
    "diagnosis":            {"en": "Diagnosis",             "ka": "დიაგნოსტიკა"},
    "alert":                {"en": "Alert",                 "ka": "გაფრთხილება"},
    "period":               {"en": "Period",                "ka": "პერიოდი"},
    "currency":             {"en": "Currency",              "ka": "ვალუტა"},
    "amount":               {"en": "Amount",                "ka": "თანხა"},
    "total":                {"en": "Total",                 "ka": "სულ"},
    "change":               {"en": "Change",                "ka": "ცვლილება"},
    "trend":                {"en": "Trend",                 "ka": "ტრენდი"},
    "forecast":             {"en": "Forecast",              "ka": "პროგნოზი"},
    "budget":               {"en": "Budget",                "ka": "ბიუჯეტი"},
    "actual":               {"en": "Actual",                "ka": "ფაქტიური"},
    "variance":             {"en": "Variance",              "ka": "გადახრა"},

    # ── Accounting Concepts ─────────────────────────────────────
    "debit":                {"en": "Debit",                 "ka": "დებეტი"},
    "credit":               {"en": "Credit",                "ka": "კრედიტი"},
    "journal_entry":        {"en": "Journal Entry",         "ka": "საბუღალტრო გატარება"},
    "trial_balance":        {"en": "Trial Balance",         "ka": "საცდელი ბალანსი"},
    "general_ledger":       {"en": "General Ledger",        "ka": "მთავარი წიგნი"},
    "chart_of_accounts":    {"en": "Chart of Accounts",     "ka": "ანგარიშთა გეგმა"},
    "fiscal_year":          {"en": "Fiscal Year",           "ka": "ფისკალური წელი"},
    "closing_entry":        {"en": "Closing Entry",         "ka": "დამხურავი გატარება"},
    "accrual":              {"en": "Accrual",               "ka": "დარიცხვა"},
    "depreciation_expense": {"en": "Depreciation Expense",  "ka": "ცვეთის ხარჯი"},
    "tax_payable":          {"en": "Tax Payable",           "ka": "გადასახდელი გადასახადი"},
    "prepaid_expense":      {"en": "Prepaid Expense",       "ka": "წინასწარ გადახდილი ხარჯი"},
}

# Reverse index: Georgian text → key
_KA_TO_KEY: Dict[str, str] = {}
for _key, _trans in _TRANSLATIONS.items():
    if "ka" in _trans:
        _KA_TO_KEY[_trans["ka"].lower()] = _key


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def t(key: str, lang: str = "en") -> str:
    """
    Translate a financial term.

    Args:
        key: Term key (e.g., "revenue", "gross_margin")
        lang: Language code ("en" or "ka")

    Returns:
        Translated string, or the key itself if not found.
    """
    entry = _TRANSLATIONS.get(key.lower())
    if entry:
        return entry.get(lang, entry.get("en", key))
    return key


def t_dict(data: Dict[str, Any], lang: str = "ka") -> Dict[str, Any]:
    """
    Translate dictionary keys to the target language.

    Args:
        data: Dict with English keys (e.g., {"revenue": 50000000})
        lang: Target language

    Returns:
        Dict with translated keys (e.g., {"შემოსავალი": 50000000})
    """
    result = {}
    for key, value in data.items():
        translated_key = t(key, lang)
        result[translated_key] = value
    return result


def get_all_terms(lang: str = "ka") -> Dict[str, str]:
    """
    Get the full translation dictionary for a language.

    Returns:
        Dict of {key: translated_term}
    """
    result = {}
    for key, trans in _TRANSLATIONS.items():
        result[key] = trans.get(lang, trans.get("en", key))
    return result


def detect_language(text: str) -> str:
    """
    Detect language of text.

    Returns:
        "ka" if Georgian characters present, "en" otherwise.
    """
    for char in text:
        if 0x10D0 <= ord(char) <= 0x10FF:
            return "ka"
    return "en"


def reverse_lookup(georgian_term: str) -> Optional[str]:
    """
    Find the English key for a Georgian term.

    Returns:
        Key string or None if not found.
    """
    return _KA_TO_KEY.get(georgian_term.lower())


def term_count() -> int:
    """Return total number of translated terms."""
    return len(_TRANSLATIONS)
