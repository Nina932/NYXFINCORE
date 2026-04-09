"""
Phase O-1: Full Double-Entry Journal System
==============================================
Production-grade double-entry bookkeeping engine:

  - JournalEntry with debit=credit validation (ALWAYS enforced)
  - GeneralLedger: post, reverse, trial balance, period close
  - Auto-journaling from P&L data
  - Account hierarchy with Georgian IFRS-compatible COA

All computations are deterministic (Decimal) — no LLM.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ACCOUNT TYPES
# ═══════════════════════════════════════════════════════════════════

class AccountType:
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"

    @staticmethod
    def from_code(code: str) -> str:
        """Determine account type from Georgian IFRS code prefix."""
        if not code:
            return AccountType.ASSET
        first = code[0]
        mapping = {
            "1": AccountType.ASSET,
            "2": AccountType.LIABILITY,
            "3": AccountType.EQUITY,
            "4": AccountType.REVENUE,
            "5": AccountType.EXPENSE,
            "6": AccountType.REVENUE,
            "7": AccountType.EXPENSE,
            "8": AccountType.EXPENSE,
            "9": AccountType.EXPENSE,
            "0": AccountType.ASSET,
        }
        return mapping.get(first, AccountType.ASSET)

    @staticmethod
    def normal_balance(acct_type: str) -> str:
        """Return normal balance side for account type."""
        if acct_type in (AccountType.ASSET, AccountType.EXPENSE):
            return "debit"
        return "credit"


# ═══════════════════════════════════════════════════════════════════
# CHART OF ACCOUNTS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Account:
    """A single account in the chart of accounts."""
    code: str
    name: str
    account_type: str
    parent_code: Optional[str] = None
    is_group: bool = False
    currency: str = "GEL"
    description: str = ""

    @property
    def normal_balance(self) -> str:
        return AccountType.normal_balance(self.account_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "account_type": self.account_type,
            "parent_code": self.parent_code,
            "is_group": self.is_group,
            "normal_balance": self.normal_balance,
            "currency": self.currency,
        }


class ChartOfAccounts:
    """
    Georgian IFRS-compatible Chart of Accounts.

    Structure:
      1xxx = Assets
      2xxx = Liabilities
      3xxx = Equity
      4xxx/6xxx = Revenue
      5xxx/7xxx = Expenses
    """

    def __init__(self):
        self._accounts: Dict[str, Account] = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load default Georgian IFRS accounts."""
        defaults = [
            # Assets
            ("1000", "Assets", AccountType.ASSET, None, True),
            ("1100", "Current Assets", AccountType.ASSET, "1000", True),
            ("1110", "Cash and Cash Equivalents", AccountType.ASSET, "1100", False),
            ("1120", "Accounts Receivable", AccountType.ASSET, "1100", False),
            ("1130", "Inventory", AccountType.ASSET, "1100", False),
            ("1140", "Prepaid Expenses", AccountType.ASSET, "1100", False),
            ("1200", "Non-Current Assets", AccountType.ASSET, "1000", True),
            ("1210", "Property, Plant & Equipment", AccountType.ASSET, "1200", False),
            ("1220", "Intangible Assets", AccountType.ASSET, "1200", False),
            ("1230", "Long-Term Investments", AccountType.ASSET, "1200", False),
            # Liabilities
            ("2000", "Liabilities", AccountType.LIABILITY, None, True),
            ("2100", "Current Liabilities", AccountType.LIABILITY, "2000", True),
            ("2110", "Accounts Payable", AccountType.LIABILITY, "2100", False),
            ("2120", "Short-Term Debt", AccountType.LIABILITY, "2100", False),
            ("2130", "Accrued Expenses", AccountType.LIABILITY, "2100", False),
            ("2140", "Tax Payable", AccountType.LIABILITY, "2100", False),
            ("2200", "Non-Current Liabilities", AccountType.LIABILITY, "2000", True),
            ("2210", "Long-Term Debt", AccountType.LIABILITY, "2200", False),
            ("2220", "Deferred Tax Liability", AccountType.LIABILITY, "2200", False),
            # Equity
            ("3000", "Equity", AccountType.EQUITY, None, True),
            ("3100", "Share Capital", AccountType.EQUITY, "3000", False),
            ("3200", "Retained Earnings", AccountType.EQUITY, "3000", False),
            ("3300", "Other Reserves", AccountType.EQUITY, "3000", False),
            # Revenue
            ("4000", "Revenue", AccountType.REVENUE, None, True),
            ("4110", "Sales Revenue", AccountType.REVENUE, "4000", False),
            ("4120", "Service Revenue", AccountType.REVENUE, "4000", False),
            ("4130", "Other Income", AccountType.REVENUE, "4000", False),
            ("6000", "Other Revenue", AccountType.REVENUE, None, True),
            ("6110", "Interest Income", AccountType.REVENUE, "6000", False),
            ("6120", "Gain on Disposal", AccountType.REVENUE, "6000", False),
            # Expenses
            ("5000", "Cost of Sales", AccountType.EXPENSE, None, True),
            ("5110", "Cost of Goods Sold", AccountType.EXPENSE, "5000", False),
            ("5120", "Direct Labor", AccountType.EXPENSE, "5000", False),
            ("5130", "Manufacturing Overhead", AccountType.EXPENSE, "5000", False),
            ("7000", "Operating Expenses", AccountType.EXPENSE, None, True),
            ("7110", "Administrative Expenses", AccountType.EXPENSE, "7000", False),
            ("7120", "Selling Expenses", AccountType.EXPENSE, "7000", False),
            ("7130", "Depreciation Expense", AccountType.EXPENSE, "7000", False),
            ("7140", "Rent Expense", AccountType.EXPENSE, "7000", False),
            ("7150", "Salary Expense", AccountType.EXPENSE, "7000", False),
            ("8000", "Financial Expenses", AccountType.EXPENSE, None, True),
            ("8110", "Interest Expense", AccountType.EXPENSE, "8000", False),
            ("8120", "Bank Charges", AccountType.EXPENSE, "8000", False),
            ("9000", "Tax Expense", AccountType.EXPENSE, None, True),
            ("9110", "Income Tax Expense", AccountType.EXPENSE, "9000", False),
        ]
        for code, name, acct_type, parent, is_group in defaults:
            self._accounts[code] = Account(code, name, acct_type, parent, is_group)

    def get_account(self, code: str) -> Optional[Account]:
        return self._accounts.get(code)

    def add_account(self, account: Account):
        self._accounts[account.code] = account

    def get_children(self, parent_code: str) -> List[Account]:
        return [a for a in self._accounts.values() if a.parent_code == parent_code]

    def get_postable_accounts(self) -> List[Account]:
        return [a for a in self._accounts.values() if not a.is_group]

    def get_by_type(self, acct_type: str) -> List[Account]:
        return [a for a in self._accounts.values() if a.account_type == acct_type]

    def all_accounts(self) -> List[Account]:
        return sorted(self._accounts.values(), key=lambda a: a.code)

    def account_count(self) -> int:
        return len(self._accounts)


# ═══════════════════════════════════════════════════════════════════
# JOURNAL ENTRY
# ═══════════════════════════════════════════════════════════════════

@dataclass
class JournalLine:
    """A single line in a journal entry."""
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    currency: str = "GEL"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "debit": float(self.debit),
            "credit": float(self.credit),
            "currency": self.currency,
            "description": self.description,
        }


@dataclass
class JournalEntry:
    """
    A complete journal entry.

    INVARIANT: sum(debits) == sum(credits) — enforced at creation.
    """
    entry_id: str
    date: str
    description: str
    reference: str
    lines: List[JournalLine]
    is_reversal: bool = False
    reversed_entry_id: Optional[str] = None
    posted: bool = False
    created_at: str = ""

    @property
    def total_debit(self) -> Decimal:
        return sum(line.debit for line in self.lines)

    @property
    def total_credit(self) -> Decimal:
        return sum(line.credit for line in self.lines)

    @property
    def is_balanced(self) -> bool:
        return abs(self.total_debit - self.total_credit) < Decimal("0.01")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "date": self.date,
            "description": self.description,
            "reference": self.reference,
            "lines": [l.to_dict() for l in self.lines],
            "total_debit": float(self.total_debit),
            "total_credit": float(self.total_credit),
            "is_balanced": self.is_balanced,
            "is_reversal": self.is_reversal,
            "posted": self.posted,
        }


class UnbalancedEntryError(ValueError):
    """Raised when a journal entry's debits don't equal credits."""
    pass


# ═══════════════════════════════════════════════════════════════════
# GENERAL LEDGER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrialBalanceRow:
    """A single row in the trial balance."""
    account_code: str
    account_name: str
    debit_balance: Decimal
    credit_balance: Decimal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "debit_balance": float(self.debit_balance),
            "credit_balance": float(self.credit_balance),
        }


@dataclass
class TrialBalance:
    """Complete trial balance."""
    rows: List[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
    as_of: str = ""
    period: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "total_debit": float(self.total_debit),
            "total_credit": float(self.total_credit),
            "is_balanced": self.is_balanced,
            "as_of": self.as_of,
            "period": self.period,
        }


class GeneralLedger:
    """
    Full double-entry general ledger.

    Posts journal entries, tracks account balances, generates trial balance,
    and handles period closing.
    """

    def __init__(self, coa: Optional[ChartOfAccounts] = None):
        self.coa = coa or ChartOfAccounts()
        self._entries: List[JournalEntry] = []
        self._account_balances: Dict[str, Decimal] = {}  # code → net balance

    def post_entry(self, entry: JournalEntry) -> JournalEntry:
        """
        Post a journal entry to the ledger.

        Raises:
            UnbalancedEntryError if debits != credits
        """
        if not entry.is_balanced:
            raise UnbalancedEntryError(
                f"Entry '{entry.entry_id}' is unbalanced: "
                f"DR={entry.total_debit} != CR={entry.total_credit}"
            )

        entry.posted = True
        entry.created_at = datetime.now(timezone.utc).isoformat()
        self._entries.append(entry)

        # Update account balances
        for line in entry.lines:
            code = line.account_code
            if code not in self._account_balances:
                self._account_balances[code] = Decimal("0")

            acct = self.coa.get_account(code)
            acct_type = acct.account_type if acct else AccountType.from_code(code)

            # Assets/Expenses increase with debit, decrease with credit
            if acct_type in (AccountType.ASSET, AccountType.EXPENSE):
                self._account_balances[code] += line.debit - line.credit
            else:
                # Liabilities/Equity/Revenue increase with credit
                self._account_balances[code] += line.credit - line.debit

        logger.info("Posted entry %s: %s (DR=%s, CR=%s)",
                     entry.entry_id, entry.description,
                     entry.total_debit, entry.total_credit)
        return entry

    def create_and_post(
        self,
        date: str,
        description: str,
        lines: List[Tuple[str, float, float]],
        reference: str = "",
    ) -> JournalEntry:
        """
        Convenience: create and post an entry in one call.

        Args:
            lines: List of (account_code, debit_amount, credit_amount)
        """
        journal_lines = []
        for code, dr, cr in lines:
            acct = self.coa.get_account(code)
            name = acct.name if acct else code
            journal_lines.append(JournalLine(
                account_code=code,
                account_name=name,
                debit=Decimal(str(dr)),
                credit=Decimal(str(cr)),
            ))

        entry = JournalEntry(
            entry_id=str(uuid.uuid4())[:8],
            date=date,
            description=description,
            reference=reference,
            lines=journal_lines,
        )
        return self.post_entry(entry)

    def reverse_entry(self, entry_id: str) -> JournalEntry:
        """Create a reversal entry for the given entry."""
        original = next((e for e in self._entries if e.entry_id == entry_id), None)
        if not original:
            raise ValueError(f"Entry not found: {entry_id}")

        reversal_lines = []
        for line in original.lines:
            reversal_lines.append(JournalLine(
                account_code=line.account_code,
                account_name=line.account_name,
                debit=line.credit,    # swap
                credit=line.debit,    # swap
                currency=line.currency,
                description=f"Reversal of: {line.description or original.description}",
            ))

        reversal = JournalEntry(
            entry_id=str(uuid.uuid4())[:8],
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            description=f"Reversal of entry {entry_id}: {original.description}",
            reference=f"REV-{entry_id}",
            lines=reversal_lines,
            is_reversal=True,
            reversed_entry_id=entry_id,
        )
        return self.post_entry(reversal)

    def get_account_balance(self, account_code: str) -> Decimal:
        """Get current balance for an account."""
        return self._account_balances.get(account_code, Decimal("0"))

    def get_account_history(
        self,
        account_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all journal lines for an account within date range."""
        history = []
        for entry in self._entries:
            if start_date and entry.date < start_date:
                continue
            if end_date and entry.date > end_date:
                continue
            for line in entry.lines:
                if line.account_code == account_code:
                    history.append({
                        "entry_id": entry.entry_id,
                        "date": entry.date,
                        "description": entry.description,
                        "debit": float(line.debit),
                        "credit": float(line.credit),
                        "reference": entry.reference,
                    })
        return history

    def trial_balance(self, period: str = "") -> TrialBalance:
        """Generate trial balance from current ledger state."""
        rows: List[TrialBalanceRow] = []
        total_dr = Decimal("0")
        total_cr = Decimal("0")

        for code in sorted(self._account_balances.keys()):
            balance = self._account_balances[code]
            if balance == 0:
                continue

            acct = self.coa.get_account(code)
            name = acct.name if acct else code
            acct_type = acct.account_type if acct else AccountType.from_code(code)

            # Debit-normal accounts show in debit column, credit-normal in credit
            if acct_type in (AccountType.ASSET, AccountType.EXPENSE):
                if balance >= 0:
                    dr, cr = balance, Decimal("0")
                else:
                    dr, cr = Decimal("0"), abs(balance)
            else:
                if balance >= 0:
                    dr, cr = Decimal("0"), balance
                else:
                    dr, cr = abs(balance), Decimal("0")

            total_dr += dr
            total_cr += cr
            rows.append(TrialBalanceRow(code, name, dr, cr))

        is_balanced = abs(total_dr - total_cr) < Decimal("0.01")

        return TrialBalance(
            rows=rows,
            total_debit=total_dr,
            total_credit=total_cr,
            is_balanced=is_balanced,
            as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            period=period,
        )

    def close_period(self, period: str) -> JournalEntry:
        """
        Close a period by moving net income to Retained Earnings (3200).

        Revenue and expense accounts are zeroed out.
        Net income = sum(revenue balances) - sum(expense balances)
        """
        lines: List[Tuple[str, float, float]] = []
        net_income = Decimal("0")

        for code, balance in self._account_balances.items():
            if balance == 0:
                continue
            acct = self.coa.get_account(code)
            acct_type = acct.account_type if acct else AccountType.from_code(code)

            if acct_type == AccountType.REVENUE:
                # Close revenue: DR revenue, CR retained earnings
                lines.append((code, float(balance), 0))
                net_income += balance
            elif acct_type == AccountType.EXPENSE:
                # Close expense: CR expense, DR retained earnings
                lines.append((code, 0, float(balance)))
                net_income -= balance

        # Transfer net income to retained earnings
        if net_income > 0:
            lines.append(("3200", 0, float(net_income)))
        elif net_income < 0:
            lines.append(("3200", float(abs(net_income)), 0))

        if not lines:
            raise ValueError("No revenue/expense accounts to close")

        return self.create_and_post(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            description=f"Period closing: {period}",
            lines=lines,
            reference=f"CLOSE-{period}",
        )

    def auto_journal_from_pl(
        self,
        date: str,
        revenue: float,
        cogs: float,
        ga_expenses: float,
        depreciation: float = 0,
        interest_expense: float = 0,
        tax_expense: float = 0,
        reference: str = "",
    ) -> List[JournalEntry]:
        """
        Auto-generate journal entries from P&L data.

        Creates separate entries for each P&L line item:
          - Revenue → CR 4110
          - COGS → DR 5110
          - G&A → DR 7110
          - Depreciation → DR 7130
          - Interest → DR 8110
          - Tax → DR 9110
        Counter-accounts use Cash (1110) or AR/AP as appropriate.
        """
        entries = []

        if revenue > 0:
            e = self.create_and_post(date, "Record revenue", [
                ("1120", revenue, 0),  # DR Accounts Receivable
                ("4110", 0, revenue),  # CR Sales Revenue
            ], f"{reference}-REV")
            entries.append(e)

        if cogs > 0:
            e = self.create_and_post(date, "Record COGS", [
                ("5110", cogs, 0),     # DR Cost of Goods Sold
                ("1130", 0, cogs),     # CR Inventory
            ], f"{reference}-COGS")
            entries.append(e)

        if ga_expenses > 0:
            e = self.create_and_post(date, "Record G&A expenses", [
                ("7110", ga_expenses, 0),  # DR Admin Expenses
                ("1110", 0, ga_expenses),  # CR Cash
            ], f"{reference}-GA")
            entries.append(e)

        if depreciation > 0:
            e = self.create_and_post(date, "Record depreciation", [
                ("7130", depreciation, 0),  # DR Depreciation Expense
                ("1210", 0, depreciation),  # CR PP&E (accumulated)
            ], f"{reference}-DEP")
            entries.append(e)

        if interest_expense > 0:
            e = self.create_and_post(date, "Record interest expense", [
                ("8110", interest_expense, 0),  # DR Interest Expense
                ("1110", 0, interest_expense),   # CR Cash
            ], f"{reference}-INT")
            entries.append(e)

        if tax_expense > 0:
            e = self.create_and_post(date, "Record tax expense", [
                ("9110", tax_expense, 0),    # DR Tax Expense
                ("2140", 0, tax_expense),    # CR Tax Payable
            ], f"{reference}-TAX")
            entries.append(e)

        return entries

    def entry_count(self) -> int:
        return len(self._entries)

    def get_entries(self, limit: int = 50) -> List[JournalEntry]:
        return self._entries[-limit:]

    def reset(self):
        """Clear all entries (for testing)."""
        self._entries.clear()
        self._account_balances.clear()


# Module-level singleton
general_ledger = GeneralLedger()
