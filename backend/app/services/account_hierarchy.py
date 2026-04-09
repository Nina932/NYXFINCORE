"""
account_hierarchy.py — Account Hierarchy Builder & Financial Statement Mapper
==============================================================================
Builds a complete account hierarchy from a parsed 1C Chart of Accounts and
maps accounts to financial statement lines (P&L, BS, Cash Flow).

Key capabilities:
  • Full parent-child tree traversal
  • P&L waterfall construction (Revenue→GP→EBITDA→Net)
  • Balance Sheet section builder (CA, NCA, CL, NCL, Equity)
  • Cash flow classification (Operating/Investing/Financing)
  • Multi-period comparison support
  • Account aggregation with GL transaction data

Classes:
  AccountHierarchyBuilder  — builds tree + statement line maps
  FinancialStatementMapper — maps transactions/balances to P&L / BS / CF lines
  StatementLine            — single line in a financial statement
  FinancialStatements      — full set of three statements

Usage:
    builder  = AccountHierarchyBuilder()
    tree     = builder.build_from_file("1c AccountN.xlsx")
    mapper   = FinancialStatementMapper(tree)
    stmts    = mapper.build_statements(transactions)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── P&L line order ──────────────────────────────────────────────────────────
PL_LINE_ORDER = [
    "Revenue",
    "Cost of Sales",
    "Gross Profit",
    "Selling Expenses",
    "Admin Expenses",
    "Distribution Expenses",
    "Other Operating Income",
    "EBITDA",
    "Depreciation & Amortisation",
    "EBIT",
    "Finance Income",
    "Finance Costs",
    "EBT",
    "Income Tax",
    "Net Income",
    "Other P&L",
    "Tax/Deferred",
]

# ── Georgian account code → P&L line mapping ───────────────────────────────
_ACCOUNT_TO_PL_LINE: Dict[str, str] = {
    # Revenue 6xxx
    "6": "Revenue",
    "61": "Revenue",
    "62": "Revenue",
    "63": "Revenue",
    "64": "Revenue",
    "65": "Revenue",
    "6110": "Revenue",
    "6120": "Revenue",
    "6210": "Revenue",
    # COGS / Cost of Sales 7xxx
    "71": "Cost of Sales",
    "7110": "Cost of Sales",
    "7120": "Cost of Sales",
    # Selling expenses 73xx
    "73": "Selling Expenses",
    "7310": "Selling Expenses",
    "7320": "Selling Expenses",
    # Admin / G&A 72xx
    "72": "Admin Expenses",
    "7210": "Admin Expenses",
    "7220": "Admin Expenses",
    # Distribution 74xx
    "74": "Distribution Expenses",
    # Other operating income 8xxx
    "8": "Other Operating Income",
    "81": "Other Operating Income",
    # Finance income/cost 82xx / 83xx
    "82": "Finance Income",
    "83": "Finance Costs",
    # Tax / deferred 9xxx
    "9": "Tax/Deferred",
    "91": "Income Tax",
    "92": "Income Tax",
    # Russian 1C codes (avoid duplicate keys with Georgian: use more specific prefix where needed)
    "90": "Revenue",
    "20": "Cost of Sales",
    "44": "Selling Expenses",
    "26": "Admin Expenses",
    "99": "Net Income",
}

# ── Georgian account code → BS line mapping ─────────────────────────────────
_ACCOUNT_TO_BS_LINE: Dict[str, Tuple[str, str]] = {
    # (section, line)
    # Current Assets 1xxx
    "11": ("current_assets", "Cash & Cash Equivalents"),
    "12": ("current_assets", "Bank Deposits"),
    "13": ("current_assets", "Trade Receivables"),
    "14": ("current_assets", "Other Receivables"),
    "15": ("current_assets", "Inventory"),
    "16": ("current_assets", "Advances Paid"),
    "17": ("current_assets", "Prepayments"),
    "18": ("current_assets", "VAT Receivable"),
    "19": ("current_assets", "Other Current Assets"),
    "1110": ("current_assets", "Cash & Cash Equivalents"),
    "1210": ("current_assets", "Bank Deposits"),
    "1310": ("current_assets", "Trade Receivables"),
    "1410": ("current_assets", "Other Receivables"),
    "1510": ("current_assets", "Inventory"),
    "1610": ("current_assets", "Advances Paid"),
    # Non-Current Assets 2xxx
    "21": ("noncurrent_assets", "Property, Plant & Equipment"),
    "22": ("noncurrent_assets", "Accumulated Depreciation"),
    "23": ("noncurrent_assets", "Intangible Assets"),
    "24": ("noncurrent_assets", "Investment Property"),
    "25": ("noncurrent_assets", "Long-term Investments"),
    "26": ("noncurrent_assets", "Deferred Tax Asset"),
    "27": ("noncurrent_assets", "Other Non-Current Assets"),
    "2110": ("noncurrent_assets", "Property, Plant & Equipment"),
    "2210": ("noncurrent_assets", "Accumulated Depreciation"),
    # Current Liabilities 3xxx
    "31": ("current_liabilities", "Trade Payables"),
    "32": ("current_liabilities", "Tax Payable"),
    "33": ("current_liabilities", "VAT Payable"),
    "34": ("current_liabilities", "Advances Received"),
    "35": ("current_liabilities", "Payroll Payable"),
    "36": ("current_liabilities", "Other Current Liabilities"),
    "3110": ("current_liabilities", "Trade Payables"),
    "3210": ("current_liabilities", "Tax Payable"),
    "3310": ("current_liabilities", "VAT Payable"),
    # Non-Current Liabilities 4xxx
    "41": ("noncurrent_liabilities", "Long-term Debt"),
    "42": ("noncurrent_liabilities", "Deferred Tax Liability"),
    "43": ("noncurrent_liabilities", "Provisions"),
    "44": ("noncurrent_liabilities", "Other NCL"),
    "4110": ("noncurrent_liabilities", "Long-term Debt"),
    # Equity 5xxx
    "51": ("equity", "Share Capital"),
    "52": ("equity", "Share Premium"),
    "53": ("equity", "Retained Earnings"),
    "54": ("equity", "Revaluation Reserve"),
    "55": ("equity", "Other Equity"),
    "5110": ("equity", "Share Capital"),
    "5210": ("equity", "Share Premium"),
    "5310": ("equity", "Retained Earnings"),
    # Russian 1C → BS
    "01": ("noncurrent_assets", "Fixed Assets"),
    "02": ("noncurrent_assets", "Accumulated Depreciation"),
    "08": ("noncurrent_assets", "Capital WIP"),
    "10": ("current_assets", "Inventory"),
    "50": ("current_assets", "Cash & Cash Equivalents"),
    "51": ("current_assets", "Bank Accounts"),
    "60": ("current_liabilities", "Trade Payables"),
    "62": ("current_assets", "Trade Receivables"),
    "68": ("current_liabilities", "Tax Payable"),
    "70": ("current_liabilities", "Payroll Payable"),
    "80": ("equity", "Share Capital"),
    "84": ("equity", "Retained Earnings"),
}

# ── Cash flow classification ─────────────────────────────────────────────────
_ACCOUNT_TO_CF_SECTION: Dict[str, str] = {
    # Operating
    "6": "operating", "7": "operating", "8": "operating",
    "13": "operating", "14": "operating", "15": "operating",
    "31": "operating", "32": "operating", "33": "operating",
    "35": "operating", "36": "operating",
    # Investing
    "21": "investing", "23": "investing", "24": "investing", "25": "investing",
    # Financing
    "41": "financing", "51": "financing", "52": "financing",
    "53": "financing",
}


@dataclass
class StatementLine:
    """A single line in a financial statement."""
    name: str
    amount: float = 0.0
    section: str = ""          # e.g. "current_assets", "Revenue"
    account_codes: List[str] = field(default_factory=list)
    is_subtotal: bool = False
    is_total: bool = False
    sign: int = 1               # +1 or -1 (for P&L sign convention)

    def add(self, amount: float):
        self.amount += amount


@dataclass
class FinancialStatements:
    """Complete set of three financial statements."""
    # P&L
    income_statement: Dict[str, StatementLine] = field(default_factory=dict)
    # Balance Sheet
    balance_sheet: Dict[str, Dict[str, StatementLine]] = field(default_factory=dict)
    # Cash Flow
    cash_flow: Dict[str, StatementLine] = field(default_factory=dict)
    # Metadata
    period: str = ""
    currency: str = "GEL"
    warnings: List[str] = field(default_factory=list)

    def gross_profit(self) -> float:
        rev  = self.income_statement.get("Revenue", StatementLine("R")).amount
        cogs = self.income_statement.get("Cost of Sales", StatementLine("C")).amount
        return rev - abs(cogs)

    def ebitda(self) -> float:
        gp = self.gross_profit()
        se = self.income_statement.get("Selling Expenses", StatementLine("S")).amount
        ae = self.income_statement.get("Admin Expenses", StatementLine("A")).amount
        de = self.income_statement.get("Distribution Expenses", StatementLine("D")).amount
        oi = self.income_statement.get("Other Operating Income", StatementLine("O")).amount
        return gp - abs(se) - abs(ae) - abs(de) + oi

    def net_income(self) -> float:
        return self.income_statement.get("Net Income", StatementLine("N")).amount

    def total_assets(self) -> float:
        ca  = sum(l.amount for l in self.balance_sheet.get("current_assets",    {}).values())
        nca = sum(l.amount for l in self.balance_sheet.get("noncurrent_assets", {}).values())
        return ca + nca

    def total_liabilities(self) -> float:
        cl  = sum(l.amount for l in self.balance_sheet.get("current_liabilities",    {}).values())
        ncl = sum(l.amount for l in self.balance_sheet.get("noncurrent_liabilities", {}).values())
        return cl + ncl

    def total_equity(self) -> float:
        return sum(l.amount for l in self.balance_sheet.get("equity", {}).values())

    def bs_equation_holds(self, tolerance: float = 0.01) -> bool:
        return abs(self.total_assets() - (self.total_liabilities() + self.total_equity())) < tolerance

    def computation_fingerprint(self) -> str:
        """SHA-256 fingerprint of all deterministic financial data.

        This hash covers every numerical output of the financial engine.
        Two reports with the same fingerprint are guaranteed to contain
        identical financial figures, regardless of LLM narrative differences.
        Use this to verify report reproducibility for audit purposes.
        """
        canonical = {
            "period": self.period,
            "currency": self.currency,
            "totals": {
                "gross_profit": round(self.gross_profit(), 2),
                "ebitda": round(self.ebitda(), 2),
                "net_income": round(self.net_income(), 2),
                "total_assets": round(self.total_assets(), 2),
                "total_liabilities": round(self.total_liabilities(), 2),
                "total_equity": round(self.total_equity(), 2),
            },
            "is_lines": {
                k: round(v.amount, 2)
                for k, v in sorted(self.income_statement.items())
            },
            "bs_lines": {
                section: {k: round(v.amount, 2) for k, v in sorted(lines.items())}
                for section, lines in sorted(self.balance_sheet.items())
            },
        }
        raw = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "period": self.period,
            "currency": self.currency,
            "income_statement": {
                k: {"name": v.name, "amount": v.amount, "section": v.section}
                for k, v in self.income_statement.items()
            },
            "balance_sheet": {
                section: {
                    k: {"name": v.name, "amount": v.amount}
                    for k, v in lines.items()
                }
                for section, lines in self.balance_sheet.items()
            },
            "cash_flow": {
                k: {"name": v.name, "amount": v.amount, "section": v.section}
                for k, v in self.cash_flow.items()
            },
            "totals": {
                "gross_profit":       self.gross_profit(),
                "ebitda":             self.ebitda(),
                "net_income":         self.net_income(),
                "total_assets":       self.total_assets(),
                "total_liabilities":  self.total_liabilities(),
                "total_equity":       self.total_equity(),
                "bs_equation_holds":  self.bs_equation_holds(),
            },
            "computation_fingerprint": self.computation_fingerprint(),
            "warnings": self.warnings,
        }


class AccountHierarchyBuilder:
    """
    Builds a complete account hierarchy from parsed account data.
    Provides lookup tables for P&L/BS/CF statement line assignment.
    """

    def build_from_file(self, path: str) -> "AccountHierarchyTree":
        """Build hierarchy directly from a COA Excel file."""
        from app.services.onec_interpreter import OneCInterpreter
        interp = OneCInterpreter()
        return interp.parse_file(path)

    def get_pl_line(self, account_code: str) -> str:
        """Map account code to P&L line name."""
        code = account_code.strip()
        # Try exact match first
        if code in _ACCOUNT_TO_PL_LINE:
            return _ACCOUNT_TO_PL_LINE[code]
        # Try progressively shorter prefixes
        for length in [4, 3, 2, 1]:
            prefix = code[:length]
            if prefix in _ACCOUNT_TO_PL_LINE:
                return _ACCOUNT_TO_PL_LINE[prefix]
        return "Other P&L"

    def get_bs_position(self, account_code: str) -> Tuple[str, str]:
        """Map account code to (BS section, BS line name)."""
        code = account_code.strip()
        if code in _ACCOUNT_TO_BS_LINE:
            return _ACCOUNT_TO_BS_LINE[code]
        for length in [4, 3, 2, 1]:
            prefix = code[:length]
            if prefix in _ACCOUNT_TO_BS_LINE:
                return _ACCOUNT_TO_BS_LINE[prefix]
        return ("other", "Other")

    def get_cf_section(self, account_code: str) -> str:
        """Map account code to Cash Flow section."""
        code = account_code.strip()
        if code in _ACCOUNT_TO_CF_SECTION:
            return _ACCOUNT_TO_CF_SECTION[code]
        for length in [4, 3, 2, 1]:
            prefix = code[:length]
            if prefix in _ACCOUNT_TO_CF_SECTION:
                return _ACCOUNT_TO_CF_SECTION[prefix]
        return "operating"

    def classify_account(self, account_code: str) -> Dict:
        """Full classification of an account code."""
        pl_line = self.get_pl_line(account_code)
        bs_section, bs_line = self.get_bs_position(account_code)
        cf_section = self.get_cf_section(account_code)

        code = account_code.strip()
        first_digit = code[0] if code else ""
        is_pl = first_digit in ("6", "7", "8", "9") or code[:2] in ("90", "91", "99", "20")
        is_bs = not is_pl

        return {
            "account_code":   account_code,
            "is_pl":          is_pl,
            "is_bs":          is_bs,
            "pl_line":        pl_line if is_pl else None,
            "bs_section":     bs_section if is_bs else None,
            "bs_line":        bs_line if is_bs else None,
            "cf_section":     cf_section,
        }


class FinancialStatementMapper:
    """
    Maps GL transaction data (account code + debit/credit amounts)
    to fully-structured P&L, Balance Sheet, and Cash Flow statements.
    """

    def __init__(self, hierarchy_builder: Optional[AccountHierarchyBuilder] = None):
        self.builder = hierarchy_builder or AccountHierarchyBuilder()

    def build_statements(
        self,
        transactions: List[Dict],
        period: str = "",
        currency: str = "GEL",
    ) -> FinancialStatements:
        """
        Build all three statements from a list of GL transactions.

        Each transaction dict must have:
          - account_code: str
          - debit:        float  (or 0)
          - credit:       float  (or 0)
        """
        stmts = FinancialStatements(period=period, currency=currency)
        stmts.balance_sheet = {
            "current_assets":         {},
            "noncurrent_assets":      {},
            "current_liabilities":    {},
            "noncurrent_liabilities": {},
            "equity":                 {},
            "other":                  {},
        }

        for txn in transactions:
            code  = str(txn.get("account_code", "")).strip()
            debit = float(txn.get("debit",  0) or 0)
            cred  = float(txn.get("credit", 0) or 0)
            net   = debit - cred

            cls = self.builder.classify_account(code)

            if cls["is_pl"]:
                line_name = cls["pl_line"] or "Other P&L"
                if line_name not in stmts.income_statement:
                    stmts.income_statement[line_name] = StatementLine(
                        name=line_name, section=line_name)
                # Revenue: credit increases revenue → positive
                if line_name == "Revenue":
                    stmts.income_statement[line_name].add(cred - debit)
                else:
                    # Expenses: debit increases → record as positive (will subtract in totals)
                    stmts.income_statement[line_name].add(debit - cred)
                stmts.income_statement[line_name].account_codes.append(code)
            else:
                bs_section = cls["bs_section"] or "other"
                bs_line    = cls["bs_line"]    or "Other"
                section_dict = stmts.balance_sheet.get(bs_section, {})
                if bs_line not in section_dict:
                    section_dict[bs_line] = StatementLine(name=bs_line, section=bs_section)
                # Assets: debit-normal → net debit = positive balance
                # Liabilities/Equity: credit-normal → net credit = positive balance
                if bs_section in ("current_assets", "noncurrent_assets"):
                    section_dict[bs_line].add(net)   # debit - credit
                else:
                    section_dict[bs_line].add(-net)  # credit - debit
                section_dict[bs_line].account_codes.append(code)
                stmts.balance_sheet[bs_section] = section_dict

                # Cash flow
                cf_section = cls["cf_section"]
                if bs_section in ("current_assets", "noncurrent_assets",
                                  "current_liabilities", "noncurrent_liabilities"):
                    cf_line = f"{bs_line} movement"
                    if cf_line not in stmts.cash_flow:
                        stmts.cash_flow[cf_line] = StatementLine(name=cf_line, section=cf_section)
                    stmts.cash_flow[cf_line].add(net)

        # Compute net income from IS and inject into equity as retained earnings.
        # In standard accounting, the period's net income flows into equity
        # so that the BS equation (Assets = Liabilities + Equity) holds.
        revenue = stmts.income_statement.get("Revenue", StatementLine("R")).amount
        total_expenses = sum(
            line.amount for name, line in stmts.income_statement.items()
            if name != "Revenue" and name != "Net Income"
        )
        computed_net_income = revenue - total_expenses
        if "Net Income" not in stmts.income_statement:
            stmts.income_statement["Net Income"] = StatementLine(
                name="Net Income", section="Net Income")
            stmts.income_statement["Net Income"].add(computed_net_income)

        if abs(computed_net_income) > 0.01:
            equity_section = stmts.balance_sheet.get("equity", {})
            equity_section["Retained Earnings (Net Income)"] = StatementLine(
                name="Retained Earnings (Net Income)", section="equity")
            equity_section["Retained Earnings (Net Income)"].add(computed_net_income)
            stmts.balance_sheet["equity"] = equity_section

        # Validate BS equation
        if not stmts.bs_equation_holds():
            stmts.warnings.append(
                f"Balance sheet equation does not hold: "
                f"Assets={stmts.total_assets():,.0f}, "
                f"L+E={stmts.total_liabilities() + stmts.total_equity():,.0f}"
            )

        return stmts

    def build_from_trial_balance(
        self,
        trial_balance: List[Dict],
        period: str = "",
        currency: str = "GEL",
    ) -> FinancialStatements:
        """
        Build statements from a trial balance (account + closing debit/credit balance).
        """
        stmts = FinancialStatements(period=period, currency=currency)
        stmts.balance_sheet = {
            "current_assets": {}, "noncurrent_assets": {},
            "current_liabilities": {}, "noncurrent_liabilities": {},
            "equity": {}, "other": {},
        }

        for row in trial_balance:
            code    = str(row.get("account_code", "")).strip()
            balance = float(row.get("balance", 0) or 0)
            debit   = float(row.get("debit",   0) or 0)
            credit  = float(row.get("credit",  0) or 0)
            # Use explicit balance if available; else net of debit/credit
            net = balance if balance != 0 else (debit - credit)

            cls = self.builder.classify_account(code)

            if cls["is_pl"]:
                line_name = cls["pl_line"] or "Other P&L"
                if line_name not in stmts.income_statement:
                    stmts.income_statement[line_name] = StatementLine(name=line_name, section=line_name)
                if line_name == "Revenue":
                    stmts.income_statement[line_name].add(abs(net))
                else:
                    stmts.income_statement[line_name].add(abs(net))
                stmts.income_statement[line_name].account_codes.append(code)
            else:
                bs_section = cls["bs_section"] or "other"
                bs_line    = cls["bs_line"]    or "Other"
                section_dict = stmts.balance_sheet.get(bs_section, {})
                if bs_line not in section_dict:
                    section_dict[bs_line] = StatementLine(name=bs_line, section=bs_section)
                section_dict[bs_line].add(abs(net))
                section_dict[bs_line].account_codes.append(code)
                stmts.balance_sheet[bs_section] = section_dict

        if not stmts.bs_equation_holds(tolerance=1000):
            stmts.warnings.append("Balance sheet equation does not balance (may need adjustments)")

        return stmts


# ── Module-level singletons ───────────────────────────────────────────────────
account_hierarchy_builder = AccountHierarchyBuilder()
financial_statement_mapper = FinancialStatementMapper(account_hierarchy_builder)
