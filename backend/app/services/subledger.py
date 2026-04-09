"""
FinAI Sub-Ledger System — AR, AP, Fixed Assets
Real sub-ledger logic with IAS 16 depreciation, date-based aging, GL reconciliation.
"""
from __future__ import annotations

import uuid
import math
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def _today() -> date:
    return date.today()


def _uid(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{short}" if prefix else short


# ═══════════════════════════════════════════════════════════════════════════
#  1. Accounts Receivable (AR)
# ═══════════════════════════════════════════════════════════════════════════

class InvoiceStatus(str, Enum):
    OPEN = "open"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


@dataclass
class AREntry:
    invoice_id: str
    customer: str
    amount: float
    currency: str
    issue_date: date
    due_date: date
    paid_date: Optional[date] = None
    status: InvoiceStatus = InvoiceStatus.OPEN
    amount_paid: float = 0.0

    @property
    def balance(self) -> float:
        return round(self.amount - self.amount_paid, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["issue_date"] = self.issue_date.isoformat()
        d["due_date"] = self.due_date.isoformat()
        d["paid_date"] = self.paid_date.isoformat() if self.paid_date else None
        d["status"] = self.status.value
        d["balance"] = self.balance
        return d


class ARSubledger:
    """Accounts Receivable sub-ledger."""

    def __init__(self):
        self._entries: Dict[str, AREntry] = {}

    # ── mutations ────────────────────────────────────────────────────────

    def add_invoice(
        self,
        customer: str,
        amount: float,
        due_date: date,
        *,
        currency: str = "GEL",
        issue_date: Optional[date] = None,
        invoice_id: Optional[str] = None,
    ) -> AREntry:
        iid = invoice_id or _uid("INV")
        entry = AREntry(
            invoice_id=iid,
            customer=customer,
            amount=round(amount, 2),
            currency=currency,
            issue_date=issue_date or _today(),
            due_date=due_date,
        )
        self._entries[iid] = entry
        self._refresh_overdue()
        return entry

    def record_payment(
        self, invoice_id: str, amount: float, payment_date: Optional[date] = None
    ) -> AREntry:
        entry = self._entries.get(invoice_id)
        if entry is None:
            raise KeyError(f"Invoice {invoice_id} not found")
        entry.amount_paid = round(entry.amount_paid + amount, 2)
        if entry.amount_paid >= entry.amount:
            entry.amount_paid = entry.amount
            entry.status = InvoiceStatus.PAID
            entry.paid_date = payment_date or _today()
        else:
            entry.status = InvoiceStatus.PARTIAL
        return entry

    # ── queries ──────────────────────────────────────────────────────────

    def get_aging_report(self, as_of: Optional[date] = None) -> dict:
        ref = as_of or _today()
        buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
        bucket_items: Dict[str, list] = {k: [] for k in buckets}

        for e in self._entries.values():
            if e.status == InvoiceStatus.PAID:
                continue
            bal = e.balance
            if bal <= 0:
                continue
            days_past = (ref - e.due_date).days
            if days_past <= 0:
                bk = "current"
            elif days_past <= 30:
                bk = "1_30"
            elif days_past <= 60:
                bk = "31_60"
            elif days_past <= 90:
                bk = "61_90"
            else:
                bk = "over_90"
            buckets[bk] = round(buckets[bk] + bal, 2)
            bucket_items[bk].append(e.to_dict())

        total = round(sum(buckets.values()), 2)
        return {
            "as_of": ref.isoformat(),
            "buckets": buckets,
            "items": bucket_items,
            "total_outstanding": total,
        }

    def get_customer_balance(self, customer: str) -> float:
        return round(
            sum(e.balance for e in self._entries.values()
                if e.customer == customer and e.status != InvoiceStatus.PAID),
            2,
        )

    def get_overdue(self, as_of: Optional[date] = None) -> List[dict]:
        ref = as_of or _today()
        self._refresh_overdue(ref)
        return [
            e.to_dict()
            for e in self._entries.values()
            if e.status == InvoiceStatus.OVERDUE
        ]

    def reconcile_with_gl(self, gl_receivables_total: float) -> dict:
        sub_total = round(
            sum(e.balance for e in self._entries.values() if e.status != InvoiceStatus.PAID), 2
        )
        diff = round(sub_total - gl_receivables_total, 2)
        return {
            "subledger_total": sub_total,
            "gl_total": gl_receivables_total,
            "difference": diff,
            "reconciled": abs(diff) < 0.01,
        }

    def list_all(self) -> List[dict]:
        return [e.to_dict() for e in self._entries.values()]

    # ── internal ─────────────────────────────────────────────────────────

    def _refresh_overdue(self, ref: Optional[date] = None):
        ref = ref or _today()
        for e in self._entries.values():
            if e.status in (InvoiceStatus.OPEN, InvoiceStatus.PARTIAL):
                if ref > e.due_date:
                    e.status = InvoiceStatus.OVERDUE


# ═══════════════════════════════════════════════════════════════════════════
#  2. Accounts Payable (AP)
# ═══════════════════════════════════════════════════════════════════════════

class BillStatus(str, Enum):
    OPEN = "open"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


@dataclass
class APEntry:
    bill_id: str
    vendor: str
    amount: float
    currency: str
    received_date: date
    due_date: date
    paid_date: Optional[date] = None
    status: BillStatus = BillStatus.OPEN
    amount_paid: float = 0.0

    @property
    def balance(self) -> float:
        return round(self.amount - self.amount_paid, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["received_date"] = self.received_date.isoformat()
        d["due_date"] = self.due_date.isoformat()
        d["paid_date"] = self.paid_date.isoformat() if self.paid_date else None
        d["status"] = self.status.value
        d["balance"] = self.balance
        return d


class APSubledger:
    """Accounts Payable sub-ledger."""

    def __init__(self):
        self._entries: Dict[str, APEntry] = {}

    # ── mutations ────────────────────────────────────────────────────────

    def add_bill(
        self,
        vendor: str,
        amount: float,
        due_date: date,
        *,
        currency: str = "GEL",
        received_date: Optional[date] = None,
        bill_id: Optional[str] = None,
    ) -> APEntry:
        bid = bill_id or _uid("BILL")
        entry = APEntry(
            bill_id=bid,
            vendor=vendor,
            amount=round(amount, 2),
            currency=currency,
            received_date=received_date or _today(),
            due_date=due_date,
        )
        self._entries[bid] = entry
        self._refresh_overdue()
        return entry

    def record_payment(
        self, bill_id: str, amount: float, payment_date: Optional[date] = None
    ) -> APEntry:
        entry = self._entries.get(bill_id)
        if entry is None:
            raise KeyError(f"Bill {bill_id} not found")
        entry.amount_paid = round(entry.amount_paid + amount, 2)
        if entry.amount_paid >= entry.amount:
            entry.amount_paid = entry.amount
            entry.status = BillStatus.PAID
            entry.paid_date = payment_date or _today()
        else:
            entry.status = BillStatus.PARTIAL
        return entry

    # ── queries ──────────────────────────────────────────────────────────

    def get_aging_report(self, as_of: Optional[date] = None) -> dict:
        ref = as_of or _today()
        buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
        bucket_items: Dict[str, list] = {k: [] for k in buckets}

        for e in self._entries.values():
            if e.status == BillStatus.PAID:
                continue
            bal = e.balance
            if bal <= 0:
                continue
            days_past = (ref - e.due_date).days
            if days_past <= 0:
                bk = "current"
            elif days_past <= 30:
                bk = "1_30"
            elif days_past <= 60:
                bk = "31_60"
            elif days_past <= 90:
                bk = "61_90"
            else:
                bk = "over_90"
            buckets[bk] = round(buckets[bk] + bal, 2)
            bucket_items[bk].append(e.to_dict())

        total = round(sum(buckets.values()), 2)
        return {
            "as_of": ref.isoformat(),
            "buckets": buckets,
            "items": bucket_items,
            "total_outstanding": total,
        }

    def get_vendor_balance(self, vendor: str) -> float:
        return round(
            sum(e.balance for e in self._entries.values()
                if e.vendor == vendor and e.status != BillStatus.PAID),
            2,
        )

    def get_payment_schedule(self, days_forward: int = 90, as_of: Optional[date] = None) -> List[dict]:
        ref = as_of or _today()
        cutoff = ref + timedelta(days=days_forward)
        upcoming = []
        for e in self._entries.values():
            if e.status == BillStatus.PAID:
                continue
            if e.due_date <= cutoff:
                upcoming.append(e.to_dict())
        upcoming.sort(key=lambda x: x["due_date"])
        return {
            "as_of": ref.isoformat(),
            "days_forward": days_forward,
            "payments": upcoming,
            "total_due": round(sum(p["balance"] for p in upcoming), 2),
        }

    def get_overdue(self, as_of: Optional[date] = None) -> List[dict]:
        ref = as_of or _today()
        self._refresh_overdue(ref)
        return [
            e.to_dict()
            for e in self._entries.values()
            if e.status == BillStatus.OVERDUE
        ]

    def reconcile_with_gl(self, gl_payables_total: float) -> dict:
        sub_total = round(
            sum(e.balance for e in self._entries.values() if e.status != BillStatus.PAID), 2
        )
        diff = round(sub_total - gl_payables_total, 2)
        return {
            "subledger_total": sub_total,
            "gl_total": gl_payables_total,
            "difference": diff,
            "reconciled": abs(diff) < 0.01,
        }

    def list_all(self) -> List[dict]:
        return [e.to_dict() for e in self._entries.values()]

    # ── internal ─────────────────────────────────────────────────────────

    def _refresh_overdue(self, ref: Optional[date] = None):
        ref = ref or _today()
        for e in self._entries.values():
            if e.status in (BillStatus.OPEN, BillStatus.PARTIAL):
                if ref > e.due_date:
                    e.status = BillStatus.OVERDUE


# ═══════════════════════════════════════════════════════════════════════════
#  3. Fixed Assets (FA) — IAS 16 compliant depreciation
# ═══════════════════════════════════════════════════════════════════════════

class AssetCategory(str, Enum):
    BUILDINGS = "buildings"
    VEHICLES = "vehicles"
    EQUIPMENT = "equipment"
    IT = "IT"
    FURNITURE = "furniture"


class DepreciationMethod(str, Enum):
    STRAIGHT_LINE = "straight_line"
    DECLINING_BALANCE = "declining_balance"


class AssetStatus(str, Enum):
    ACTIVE = "active"
    DISPOSED = "disposed"


@dataclass
class AssetDisposal:
    disposal_date: date
    disposal_amount: float
    nbv_at_disposal: float
    gain_loss: float


@dataclass
class FixedAsset:
    asset_id: str
    name: str
    category: AssetCategory
    acquisition_date: date
    acquisition_cost: float
    useful_life_years: int
    residual_value: float
    depreciation_method: DepreciationMethod
    status: AssetStatus = AssetStatus.ACTIVE
    disposal: Optional[AssetDisposal] = None

    @property
    def depreciable_amount(self) -> float:
        """IAS 16.6 — cost less residual value."""
        return round(self.acquisition_cost - self.residual_value, 2)

    def to_dict(self) -> dict:
        d = {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category.value,
            "acquisition_date": self.acquisition_date.isoformat(),
            "acquisition_cost": self.acquisition_cost,
            "useful_life_years": self.useful_life_years,
            "residual_value": self.residual_value,
            "depreciation_method": self.depreciation_method.value,
            "depreciable_amount": self.depreciable_amount,
            "status": self.status.value,
        }
        if self.disposal:
            d["disposal"] = {
                "disposal_date": self.disposal.disposal_date.isoformat(),
                "disposal_amount": self.disposal.disposal_amount,
                "nbv_at_disposal": self.disposal.nbv_at_disposal,
                "gain_loss": self.disposal.gain_loss,
            }
        return d


class FASubledger:
    """Fixed Assets sub-ledger with IAS 16 depreciation calculations."""

    def __init__(self):
        self._assets: Dict[str, FixedAsset] = {}

    # ── mutations ────────────────────────────────────────────────────────

    def add_asset(
        self,
        name: str,
        category: str,
        cost: float,
        useful_life: int,
        residual_value: float = 0.0,
        method: str = "straight_line",
        *,
        acquisition_date: Optional[date] = None,
        asset_id: Optional[str] = None,
    ) -> FixedAsset:
        aid = asset_id or _uid("FA")
        asset = FixedAsset(
            asset_id=aid,
            name=name,
            category=AssetCategory(category) if isinstance(category, str) else category,
            acquisition_date=acquisition_date or _today(),
            acquisition_cost=round(cost, 2),
            useful_life_years=useful_life,
            residual_value=round(residual_value, 2),
            depreciation_method=(
                DepreciationMethod(method) if isinstance(method, str) else method
            ),
        )
        self._assets[aid] = asset
        return asset

    def dispose_asset(
        self,
        asset_id: str,
        disposal_date: date,
        disposal_amount: float,
    ) -> dict:
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(f"Asset {asset_id} not found")
        if asset.status == AssetStatus.DISPOSED:
            raise ValueError(f"Asset {asset_id} already disposed")

        accum = self.calculate_depreciation(asset_id, disposal_date)
        nbv = round(asset.acquisition_cost - accum, 2)
        gain_loss = round(disposal_amount - nbv, 2)

        asset.disposal = AssetDisposal(
            disposal_date=disposal_date,
            disposal_amount=round(disposal_amount, 2),
            nbv_at_disposal=nbv,
            gain_loss=gain_loss,
        )
        asset.status = AssetStatus.DISPOSED
        return {
            "asset_id": asset_id,
            "nbv_at_disposal": nbv,
            "disposal_amount": round(disposal_amount, 2),
            "gain_loss": gain_loss,
            "type": "gain" if gain_loss >= 0 else "loss",
        }

    # ── depreciation (IAS 16) ───────────────────────────────────────────

    def calculate_depreciation(self, asset_id: str, to_date: Optional[date] = None) -> float:
        """
        Accumulated depreciation from acquisition_date to to_date.
        IAS 16.62 — straight-line: (cost - residual) / useful_life * time
        IAS 16.62 — declining balance: rate applied to NBV each period
        Depreciation is computed monthly for precision.
        """
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(f"Asset {asset_id} not found")
        ref = to_date or _today()

        # If disposed, cap depreciation at disposal date
        if asset.disposal and ref > asset.disposal.disposal_date:
            ref = asset.disposal.disposal_date

        if ref <= asset.acquisition_date:
            return 0.0

        total_months = asset.useful_life_years * 12
        if total_months == 0:
            return 0.0

        # Elapsed full months (pro-rata monthly)
        elapsed_months = (
            (ref.year - asset.acquisition_date.year) * 12
            + (ref.month - asset.acquisition_date.month)
        )
        # Add partial month fraction for the day component
        day_fraction = 0.0
        if ref.day >= asset.acquisition_date.day:
            day_fraction = (ref.day - asset.acquisition_date.day) / 30.0
        else:
            elapsed_months -= 1
            days_in_partial = ref.day + (30 - asset.acquisition_date.day)
            day_fraction = days_in_partial / 30.0

        total_elapsed = elapsed_months + day_fraction
        if total_elapsed <= 0:
            return 0.0

        if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE:
            # IAS 16.62(a): Straight-line — equal charge over useful life
            monthly_depr = asset.depreciable_amount / total_months
            accum = monthly_depr * min(total_elapsed, total_months)
            # Cap at depreciable amount
            return round(min(accum, asset.depreciable_amount), 2)

        elif asset.depreciation_method == DepreciationMethod.DECLINING_BALANCE:
            # IAS 16.62(b): Declining balance — double-declining rate
            # Rate = 2 / useful_life_years (annual), applied monthly
            annual_rate = 2.0 / asset.useful_life_years
            monthly_rate = annual_rate / 12.0
            nbv = asset.acquisition_cost
            accum = 0.0
            months_to_calc = int(min(math.ceil(total_elapsed), total_months))

            for m in range(months_to_calc):
                if nbv <= asset.residual_value:
                    break
                depr = nbv * monthly_rate
                # Don't depreciate below residual value
                if nbv - depr < asset.residual_value:
                    depr = nbv - asset.residual_value
                accum += depr
                nbv -= depr

            # Handle partial last month
            if total_elapsed > months_to_calc and months_to_calc < total_months:
                partial = total_elapsed - months_to_calc
                if nbv > asset.residual_value:
                    depr = nbv * monthly_rate * partial
                    if nbv - depr < asset.residual_value:
                        depr = nbv - asset.residual_value
                    accum += depr

            max_depr = asset.acquisition_cost - asset.residual_value
            return round(min(accum, max_depr), 2)

        return 0.0

    def get_depreciation_schedule(self, asset_id: str) -> dict:
        """Annual depreciation schedule for the full useful life."""
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(f"Asset {asset_id} not found")

        schedule = []
        start = asset.acquisition_date

        for year_num in range(1, asset.useful_life_years + 1):
            period_end_year = start.year + year_num
            try:
                period_end = date(period_end_year, start.month, start.day)
            except ValueError:
                # Handle leap year edge case (Feb 29)
                period_end = date(period_end_year, start.month, 28)

            accum_end = self.calculate_depreciation(asset_id, period_end)
            if year_num == 1:
                accum_start = 0.0
            else:
                prev_year = start.year + (year_num - 1)
                try:
                    prev_end = date(prev_year, start.month, start.day)
                except ValueError:
                    prev_end = date(prev_year, start.month, 28)
                accum_start = self.calculate_depreciation(asset_id, prev_end)

            period_depr = round(accum_end - accum_start, 2)
            nbv = round(asset.acquisition_cost - accum_end, 2)

            schedule.append({
                "year": year_num,
                "period_end": period_end.isoformat(),
                "depreciation_expense": period_depr,
                "accumulated_depreciation": round(accum_end, 2),
                "net_book_value": nbv,
            })

        return {
            "asset_id": asset_id,
            "asset_name": asset.name,
            "method": asset.depreciation_method.value,
            "acquisition_cost": asset.acquisition_cost,
            "residual_value": asset.residual_value,
            "useful_life_years": asset.useful_life_years,
            "schedule": schedule,
        }

    def get_register(self, as_of: Optional[date] = None) -> dict:
        """Full asset register with current NBV."""
        ref = as_of or _today()
        rows = []
        total_cost = 0.0
        total_accum = 0.0
        total_nbv = 0.0

        for asset in self._assets.values():
            accum = self.calculate_depreciation(asset.asset_id, ref)
            nbv = round(asset.acquisition_cost - accum, 2)
            row = asset.to_dict()
            row["accumulated_depreciation"] = accum
            row["net_book_value"] = nbv
            rows.append(row)
            if asset.status == AssetStatus.ACTIVE:
                total_cost += asset.acquisition_cost
                total_accum += accum
                total_nbv += nbv

        return {
            "as_of": ref.isoformat(),
            "assets": rows,
            "totals": {
                "acquisition_cost": round(total_cost, 2),
                "accumulated_depreciation": round(total_accum, 2),
                "net_book_value": round(total_nbv, 2),
                "count": len([a for a in self._assets.values() if a.status == AssetStatus.ACTIVE]),
            },
        }

    def get_category_summary(self, as_of: Optional[date] = None) -> dict:
        ref = as_of or _today()
        cats: Dict[str, dict] = {}
        for asset in self._assets.values():
            if asset.status != AssetStatus.ACTIVE:
                continue
            cat = asset.category.value
            if cat not in cats:
                cats[cat] = {"count": 0, "acquisition_cost": 0.0, "accumulated_depreciation": 0.0, "net_book_value": 0.0}
            accum = self.calculate_depreciation(asset.asset_id, ref)
            nbv = round(asset.acquisition_cost - accum, 2)
            cats[cat]["count"] += 1
            cats[cat]["acquisition_cost"] = round(cats[cat]["acquisition_cost"] + asset.acquisition_cost, 2)
            cats[cat]["accumulated_depreciation"] = round(cats[cat]["accumulated_depreciation"] + accum, 2)
            cats[cat]["net_book_value"] = round(cats[cat]["net_book_value"] + nbv, 2)
        return {"as_of": ref.isoformat(), "categories": cats}

    def reconcile_with_gl(self, gl_fixed_assets: float, gl_accum_depr: float) -> dict:
        reg = self.get_register()
        sub_cost = reg["totals"]["acquisition_cost"]
        sub_accum = reg["totals"]["accumulated_depreciation"]
        cost_diff = round(sub_cost - gl_fixed_assets, 2)
        depr_diff = round(sub_accum - gl_accum_depr, 2)
        return {
            "fixed_assets": {
                "subledger": sub_cost,
                "gl": gl_fixed_assets,
                "difference": cost_diff,
                "reconciled": abs(cost_diff) < 0.01,
            },
            "accumulated_depreciation": {
                "subledger": sub_accum,
                "gl": gl_accum_depr,
                "difference": depr_diff,
                "reconciled": abs(depr_diff) < 0.01,
            },
        }

    def list_all(self) -> List[dict]:
        return [a.to_dict() for a in self._assets.values()]


# ═══════════════════════════════════════════════════════════════════════════
#  4. Unified Sub-Ledger Manager
# ═══════════════════════════════════════════════════════════════════════════

class SubledgerManager:
    """Single access point for all three sub-ledgers."""

    def __init__(self):
        self.ar = ARSubledger()
        self.ap = APSubledger()
        self.fa = FASubledger()

    def populate_from_financials(
        self,
        pnl: Optional[dict] = None,
        balance_sheet: Optional[dict] = None,
    ) -> dict:
        """
        Populate all three sub-ledgers with realistic sample entries
        derived from uploaded financial data.
        """
        pnl = pnl or {}
        bs = balance_sheet or {}
        created = {"ar": 0, "ap": 0, "fa": 0}
        today = _today()

        # ── AR from receivables balance ──────────────────────────────────
        receivables = self._extract_value(bs, [
            "accounts_receivable", "receivables", "trade_receivables",
            "Accounts Receivable", "Trade Receivables",
        ])
        if receivables and receivables > 0:
            # Split into aging buckets: 40% current, 25% 1-30, 20% 31-60, 10% 61-90, 5% 90+
            splits = [
                ("Customer Alpha", 0.40, today + timedelta(days=15)),
                ("Customer Beta", 0.25, today - timedelta(days=15)),
                ("Customer Gamma", 0.20, today - timedelta(days=45)),
                ("Customer Delta", 0.10, today - timedelta(days=75)),
                ("Customer Epsilon", 0.05, today - timedelta(days=120)),
            ]
            for cust, pct, due in splits:
                amt = round(receivables * pct, 2)
                if amt > 0:
                    issue = due - timedelta(days=30)
                    self.ar.add_invoice(cust, amt, due, issue_date=issue)
                    created["ar"] += 1

        # ── AP from payables balance ─────────────────────────────────────
        payables = self._extract_value(bs, [
            "accounts_payable", "payables", "trade_payables",
            "Accounts Payable", "Trade Payables",
        ])
        if payables and payables > 0:
            splits = [
                ("Supplier One", 0.35, today + timedelta(days=20)),
                ("Supplier Two", 0.25, today + timedelta(days=7)),
                ("Supplier Three", 0.20, today - timedelta(days=10)),
                ("Supplier Four", 0.12, today - timedelta(days=40)),
                ("Supplier Five", 0.08, today - timedelta(days=100)),
            ]
            for vendor, pct, due in splits:
                amt = round(payables * pct, 2)
                if amt > 0:
                    recv = due - timedelta(days=30)
                    self.ap.add_bill(vendor, amt, due, received_date=recv)
                    created["ap"] += 1

        # ── FA from fixed assets and depreciation ────────────────────────
        fa_total = self._extract_value(bs, [
            "fixed_assets", "property_plant_equipment", "ppe",
            "Fixed Assets", "Property Plant Equipment", "PPE",
            "non_current_assets",
        ])
        accum_depr = self._extract_value(bs, [
            "accumulated_depreciation", "depreciation",
            "Accumulated Depreciation",
        ])
        if fa_total and fa_total > 0:
            # Infer depreciation from PnL if not in BS
            if not accum_depr:
                accum_depr = abs(self._extract_value(pnl, [
                    "depreciation", "depreciation_expense",
                    "Depreciation", "D&A", "depreciation_and_amortization",
                ]) or 0)

            # Distribute across categories
            asset_templates = [
                ("Office Building", "buildings", 0.40, 25, 0.10),
                ("Fleet Vehicles", "vehicles", 0.15, 8, 0.05),
                ("Production Equipment", "equipment", 0.25, 10, 0.05),
                ("IT Infrastructure", "IT", 0.12, 5, 0.0),
                ("Office Furniture", "furniture", 0.08, 7, 0.02),
            ]
            # Estimate acquisition cost: if we have accum_depr, gross cost is
            # the reported total (which may be net or gross depending on data).
            # We assume fa_total is gross cost for safety.
            gross = fa_total if fa_total > (accum_depr or 0) else fa_total + (accum_depr or 0)

            for name, cat, pct, life, res_pct in asset_templates:
                cost = round(gross * pct, 2)
                residual = round(cost * res_pct, 2)
                if cost > 0:
                    # Back-date acquisition so depreciation approximates reported amounts
                    years_back = max(1, life // 3)
                    acq_date = date(today.year - years_back, 1, 1)
                    self.fa.add_asset(
                        name, cat, cost, life, residual,
                        "straight_line", acquisition_date=acq_date,
                    )
                    created["fa"] += 1

        return {
            "populated": True,
            "entries_created": created,
            "ar_total": self.ar.get_aging_report()["total_outstanding"],
            "ap_total": self.ap.get_aging_report()["total_outstanding"],
            "fa_count": len(self.fa._assets),
        }

    def full_reconciliation(
        self,
        gl_receivables: float = 0.0,
        gl_payables: float = 0.0,
        gl_fixed_assets: float = 0.0,
        gl_accum_depr: float = 0.0,
    ) -> dict:
        return {
            "ar": self.ar.reconcile_with_gl(gl_receivables),
            "ap": self.ap.reconcile_with_gl(gl_payables),
            "fa": self.fa.reconcile_with_gl(gl_fixed_assets, gl_accum_depr),
        }

    @staticmethod
    def _extract_value(data: dict, keys: list) -> Optional[float]:
        """Try multiple possible keys in a financial dict, return first match."""
        if not data:
            return None
        for k in keys:
            if k in data:
                val = data[k]
                if isinstance(val, (int, float)):
                    return abs(float(val))
                if isinstance(val, str):
                    try:
                        return abs(float(val.replace(",", "")))
                    except (ValueError, TypeError):
                        pass
        # Also check nested structures
        for v in data.values():
            if isinstance(v, dict):
                for k in keys:
                    if k in v:
                        val = v[k]
                        if isinstance(val, (int, float)):
                            return abs(float(val))
        return None


# ── Module-level singleton ───────────────────────────────────────────────

subledger_manager = SubledgerManager()
