"""
FinAI AR/AP/Asset Accounting Modules
======================================
SAP FI sub-modules:
- AR (Accounts Receivable): Customer invoices, aging, collection tracking
- AP (Accounts Payable): Vendor invoices, payment scheduling, cash flow impact
- Asset Accounting: Fixed asset register, depreciation schedules, impairment
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from sqlalchemy import or_

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════

@dataclass
class ARInvoice:
    invoice_id: str
    customer: str
    amount: float
    currency: str = "GEL"
    issue_date: str = ""
    due_date: str = ""
    status: str = "open"  # open, partial, paid, overdue, written_off
    paid_amount: float = 0
    days_outstanding: int = 0
    aging_bucket: str = "current"  # current, 30, 60, 90, 120+

@dataclass
class APInvoice:
    invoice_id: str
    vendor: str
    amount: float
    currency: str = "GEL"
    invoice_date: str = ""
    due_date: str = ""
    status: str = "pending"  # pending, approved, scheduled, paid, disputed
    paid_amount: float = 0
    payment_terms: str = "Net 30"
    days_until_due: int = 0

@dataclass
class FixedAsset:
    asset_id: str
    name: str
    category: str  # buildings, equipment, vehicles, intangible
    acquisition_date: str = ""
    acquisition_cost: float = 0
    useful_life_years: int = 0
    depreciation_method: str = "straight_line"  # straight_line, declining_balance, units_of_production
    accumulated_depreciation: float = 0
    net_book_value: float = 0
    status: str = "active"  # active, disposed, impaired, fully_depreciated


# ═══════════════════════════════════════════════════════════
# AR MODULE
# ═══════════════════════════════════════════════════════════

class AccountsReceivable:
    """Accounts Receivable management — customer invoices and collections."""

    def __init__(self):
        self._invoices: List[ARInvoice] = []

    async def load_from_tb(self, db) -> List[ARInvoice]:
        """Derive AR data from trial balance / posting lines."""
        from app.models.all_models import PostingLineRecord as PostingLine, JournalEntryRecord as JournalEntry
        from sqlalchemy import select

        result = await db.execute(
            select(PostingLine).join(JournalEntry)
            .where(JournalEntry.status == "posted")
            .where(or_(PostingLine.account_code.like("12%"), PostingLine.account_code.like("13%")))  # 12xx/13xx = Receivables in IFRS COA
        )
        lines = result.scalars().all()

        invoices = []
        for line in lines:
            dr = float(line.debit or 0)
            cr = float(line.credit or 0)
            amt = dr - cr
            inv = ARInvoice(
                invoice_id=f"AR-{line.id}",
                customer=line.description or "Customer",
                amount=amt,
                status="open" if amt > 0 else "paid",
                days_outstanding=0,
            )
            invoices.append(inv)

        self._invoices = invoices
        return invoices

    def aging_analysis(self) -> Dict[str, Any]:
        """Generate AR aging report (current, 30, 60, 90, 120+ days)."""
        buckets = {"current": 0, "1-30": 0, "31-60": 0, "61-90": 0, "91-120": 0, "120+": 0}
        for inv in self._invoices:
            if inv.status not in ("open", "overdue"):
                continue
            d = inv.days_outstanding
            if d <= 0:
                buckets["current"] += inv.amount
            elif d <= 30:
                buckets["1-30"] += inv.amount
            elif d <= 60:
                buckets["31-60"] += inv.amount
            elif d <= 90:
                buckets["61-90"] += inv.amount
            elif d <= 120:
                buckets["91-120"] += inv.amount
            else:
                buckets["120+"] += inv.amount

        total = sum(buckets.values())
        return {
            "total_receivables": total,
            "buckets": buckets,
            "concentration": {k: round(v / total * 100, 1) if total else 0 for k, v in buckets.items()},
            "invoice_count": len([i for i in self._invoices if i.status in ("open", "overdue")]),
            "average_days_outstanding": sum(i.days_outstanding for i in self._invoices) / len(self._invoices) if self._invoices else 0,
            "overdue_amount": buckets["31-60"] + buckets["61-90"] + buckets["91-120"] + buckets["120+"],
            "collection_risk": "high" if buckets["120+"] > total * 0.2 else ("medium" if buckets["91-120"] + buckets["120+"] > total * 0.1 else "low"),
        }

    def dso(self, revenue: float, days: int = 365) -> float:
        """Days Sales Outstanding."""
        total_ar = sum(i.amount for i in self._invoices if i.status in ("open", "overdue"))
        return (total_ar / revenue * days) if revenue else 0

    def get_summary(self, revenue: float = 0) -> Dict[str, Any]:
        aging = self.aging_analysis()
        return {
            "module": "Accounts Receivable",
            "total_invoices": len(self._invoices),
            "open_invoices": len([i for i in self._invoices if i.status in ("open", "overdue")]),
            "total_receivables": aging["total_receivables"],
            "overdue_amount": aging["overdue_amount"],
            "collection_risk": aging["collection_risk"],
            "dso": round(self.dso(revenue), 1) if revenue else None,
            "aging": aging["buckets"],
        }


# ═══════════════════════════════════════════════════════════
# AP MODULE
# ═══════════════════════════════════════════════════════════

class AccountsPayable:
    """Accounts Payable management — vendor invoices and payments."""

    def __init__(self):
        self._invoices: List[APInvoice] = []

    async def load_from_tb(self, db) -> List[APInvoice]:
        """Derive AP data from posting lines (account 33xx = payables)."""
        from app.models.all_models import PostingLineRecord as PostingLine, JournalEntryRecord as JournalEntry
        from sqlalchemy import select

        result = await db.execute(
            select(PostingLine).join(JournalEntry)
            .where(JournalEntry.status == "posted")
            .where(or_(PostingLine.account_code.like("31%"), PostingLine.account_code.like("33%")))  # 31xx/33xx = Payables
        )
        lines = result.scalars().all()

        invoices = []
        for line in lines:
            dr = float(line.debit or 0)
            cr = float(line.credit or 0)
            amt = abs(cr - dr)
            inv = APInvoice(
                invoice_id=f"AP-{line.id}",
                vendor=line.description or "Vendor",
                amount=amt,
                status="pending" if (cr - dr) > 0 else "paid",
            )
            invoices.append(inv)

        self._invoices = invoices
        return invoices

    def payment_schedule(self, days_ahead: int = 90) -> Dict[str, Any]:
        """Generate payment schedule for next N days."""
        schedule = {"week_1": 0, "week_2": 0, "month_1": 0, "month_2": 0, "month_3": 0, "beyond": 0}
        for inv in self._invoices:
            if inv.status not in ("pending", "approved", "scheduled"):
                continue
            d = inv.days_until_due
            if d <= 7:
                schedule["week_1"] += inv.amount
            elif d <= 14:
                schedule["week_2"] += inv.amount
            elif d <= 30:
                schedule["month_1"] += inv.amount
            elif d <= 60:
                schedule["month_2"] += inv.amount
            elif d <= 90:
                schedule["month_3"] += inv.amount
            else:
                schedule["beyond"] += inv.amount
        return {
            "total_payables": sum(schedule.values()),
            "schedule": schedule,
            "invoice_count": len([i for i in self._invoices if i.status in ("pending", "approved", "scheduled")]),
        }

    def dpo(self, cogs: float, days: int = 365) -> float:
        """Days Payable Outstanding."""
        total_ap = sum(i.amount for i in self._invoices if i.status in ("pending", "approved"))
        return (total_ap / cogs * days) if cogs else 0

    def get_summary(self, cogs: float = 0) -> Dict[str, Any]:
        schedule = self.payment_schedule()
        return {
            "module": "Accounts Payable",
            "total_invoices": len(self._invoices),
            "pending_invoices": len([i for i in self._invoices if i.status in ("pending", "approved")]),
            "total_payables": schedule["total_payables"],
            "next_7_days": schedule["schedule"]["week_1"],
            "next_30_days": schedule["schedule"]["week_1"] + schedule["schedule"]["week_2"] + schedule["schedule"]["month_1"],
            "dpo": round(self.dpo(cogs), 1) if cogs else None,
            "schedule": schedule["schedule"],
        }


# ═══════════════════════════════════════════════════════════
# ASSET ACCOUNTING MODULE
# ═══════════════════════════════════════════════════════════

class AssetAccounting:
    """Fixed Asset Register with depreciation tracking."""

    def __init__(self):
        self._assets: List[FixedAsset] = []

    async def load_from_tb(self, db) -> List[FixedAsset]:
        """Derive assets from posting lines (account 2xxx = non-current assets)."""
        from app.models.all_models import PostingLineRecord as PostingLine, JournalEntryRecord as JournalEntry
        from sqlalchemy import select

        result = await db.execute(
            select(PostingLine).join(JournalEntry)
            .where(JournalEntry.status == "posted")
            .where(or_(PostingLine.account_code.like("2%"), PostingLine.account_code.like("21%")))  # 2xxx/21xx = Non-current assets
        )
        lines = result.scalars().all()

        assets = []
        for line in lines:
            code = line.account_code or ""
            category = "equipment"
            if code.startswith("21"):
                category = "buildings"
            elif code.startswith("22"):
                category = "equipment"
            elif code.startswith("23"):
                category = "vehicles"
            elif code.startswith("24"):
                category = "intangible"

            dr = float(line.debit or 0)
            cr = float(line.credit or 0)
            asset = FixedAsset(
                asset_id=f"FA-{line.id}",
                name=line.description or f"Asset {code}",
                category=category,
                acquisition_cost=dr,
                net_book_value=dr - cr,
                accumulated_depreciation=cr,
                useful_life_years=10,
                status="active" if dr > cr else "fully_depreciated",
            )
            assets.append(asset)

        self._assets = assets
        return assets

    def depreciation_schedule(self, periods: int = 12) -> List[Dict[str, Any]]:
        """Generate monthly depreciation schedule for all active assets."""
        schedule = []
        for month in range(1, periods + 1):
            monthly_dep = 0
            for asset in self._assets:
                if asset.status != "active" or asset.useful_life_years == 0:
                    continue
                if asset.depreciation_method == "straight_line":
                    monthly_dep += asset.acquisition_cost / (asset.useful_life_years * 12)
                elif asset.depreciation_method == "declining_balance":
                    rate = 2 / asset.useful_life_years
                    monthly_dep += (asset.net_book_value * rate) / 12

            schedule.append({
                "month": month,
                "depreciation": round(monthly_dep, 2),
                "cumulative": round(monthly_dep * month, 2),
            })
        return schedule

    def get_summary(self) -> Dict[str, Any]:
        total_cost = sum(a.acquisition_cost for a in self._assets)
        total_dep = sum(a.accumulated_depreciation for a in self._assets)
        total_nbv = sum(a.net_book_value for a in self._assets)

        by_category = {}
        for a in self._assets:
            if a.category not in by_category:
                by_category[a.category] = {"count": 0, "cost": 0, "nbv": 0}
            by_category[a.category]["count"] += 1
            by_category[a.category]["cost"] += a.acquisition_cost
            by_category[a.category]["nbv"] += a.net_book_value

        return {
            "module": "Asset Accounting",
            "total_assets": len(self._assets),
            "active_assets": len([a for a in self._assets if a.status == "active"]),
            "total_acquisition_cost": round(total_cost, 2),
            "total_accumulated_depreciation": round(total_dep, 2),
            "total_net_book_value": round(total_nbv, 2),
            "depreciation_rate": round(total_dep / total_cost * 100, 1) if total_cost else 0,
            "by_category": {k: {"count": v["count"], "cost": round(v["cost"], 2), "nbv": round(v["nbv"], 2)} for k, v in by_category.items()},
            "next_12_months_depreciation": self.depreciation_schedule(12),
        }


# ═══════════════════════════════════════════════════════════
# COMBINED SAP FI MODULE
# ═══════════════════════════════════════════════════════════

class SAPFIModule:
    """Combined AR + AP + Asset Accounting — SAP FI equivalent."""

    def __init__(self):
        self.ar = AccountsReceivable()
        self.ap = AccountsPayable()
        self.assets = AssetAccounting()

    async def load_all(self, db):
        """Load all sub-modules from database."""
        await self.ar.load_from_tb(db)
        await self.ap.load_from_tb(db)
        await self.assets.load_from_tb(db)

    def working_capital_analysis(self, revenue: float = 0, cogs: float = 0) -> Dict[str, Any]:
        """Working capital cycle analysis."""
        ar_total = sum(i.amount for i in self.ar._invoices if i.status in ("open", "overdue"))
        ap_total = sum(i.amount for i in self.ap._invoices if i.status in ("pending", "approved"))
        dso = self.ar.dso(revenue) if revenue else 0
        dpo = self.ap.dpo(cogs) if cogs else 0
        ccc = dso - dpo  # Cash Conversion Cycle (simplified, no DIO)

        return {
            "accounts_receivable": round(ar_total, 2),
            "accounts_payable": round(ap_total, 2),
            "net_working_capital": round(ar_total - ap_total, 2),
            "dso": round(dso, 1),
            "dpo": round(dpo, 1),
            "cash_conversion_cycle": round(ccc, 1),
            "working_capital_health": "good" if ccc < 45 else ("moderate" if ccc < 90 else "poor"),
        }

    async def get_full_summary(self, db, revenue: float = 0, cogs: float = 0) -> Dict[str, Any]:
        """Complete SAP FI summary across all modules."""
        await self.load_all(db)
        return {
            "sap_fi_modules": {
                "ar": self.ar.get_summary(revenue),
                "ap": self.ap.get_summary(cogs),
                "assets": self.assets.get_summary(),
            },
            "working_capital": self.working_capital_analysis(revenue, cogs),
            "total_data_points": len(self.ar._invoices) + len(self.ap._invoices) + len(self.assets._assets),
        }


# Global instances
accounts_receivable = AccountsReceivable()
accounts_payable = AccountsPayable()
asset_accounting = AssetAccounting()
sap_fi = SAPFIModule()
