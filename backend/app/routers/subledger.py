from fastapi import APIRouter, HTTPException
from datetime import date
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subledger", tags=["subledger"])


def _mgr():
    from app.services.subledger import subledger_manager
    return subledger_manager


@router.get("/ar/aging")
async def ar_aging():
    """AR aging analysis with buckets and items."""
    try:
        mgr = _mgr()
        report = mgr.ar.get_aging_report()
        overdue = mgr.ar.get_overdue()
        all_entries = mgr.ar.list_all()

        # Compute DSO approximation
        total_outstanding = report.get("total_outstanding", 0)
        # Rough annual revenue estimate (outstanding * 365 / 45 as proxy)
        dso = 0
        if all_entries:
            today = date.today()
            weighted_days = 0
            total_bal = 0
            for e in all_entries:
                if e.get("status") == "paid":
                    continue
                bal = e.get("balance", 0)
                if bal <= 0:
                    continue
                due = date.fromisoformat(e["due_date"])
                days = max(0, (today - due).days)
                weighted_days += days * bal
                total_bal += bal
            dso = round(weighted_days / total_bal, 1) if total_bal > 0 else 0

        return {
            **report,
            "overdue_items": overdue,
            "total_entries": len(all_entries),
            "dso_estimate": dso,
        }
    except Exception as e:
        logger.error(f"AR aging error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ap/aging")
async def ap_aging():
    """AP aging analysis with buckets and items."""
    try:
        mgr = _mgr()
        report = mgr.ap.get_aging_report()
        overdue = mgr.ap.get_overdue()
        all_entries = mgr.ap.list_all()
        schedule = mgr.ap.get_payment_schedule(days_forward=90)

        # Compute DPO approximation
        dpo = 0
        if all_entries:
            today = date.today()
            weighted_days = 0
            total_bal = 0
            for e in all_entries:
                if e.get("status") == "paid":
                    continue
                bal = e.get("balance", 0)
                if bal <= 0:
                    continue
                due = date.fromisoformat(e["due_date"])
                days = max(0, (today - due).days)
                weighted_days += days * bal
                total_bal += bal
            dpo = round(weighted_days / total_bal, 1) if total_bal > 0 else 0

        return {
            **report,
            "overdue_items": overdue,
            "total_entries": len(all_entries),
            "dpo_estimate": dpo,
            "payment_schedule": schedule,
        }
    except Exception as e:
        logger.error(f"AP aging error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def subledger_summary():
    """Overall sub-ledger summary: AR, AP totals + key metrics."""
    try:
        mgr = _mgr()
        ar_report = mgr.ar.get_aging_report()
        ap_report = mgr.ap.get_aging_report()
        ar_all = mgr.ar.list_all()
        ap_all = mgr.ap.list_all()

        ar_overdue = mgr.ar.get_overdue()
        ap_overdue = mgr.ap.get_overdue()

        # Top 10 overdue AR by balance
        ar_overdue_sorted = sorted(ar_overdue, key=lambda x: x.get("balance", 0), reverse=True)[:10]
        ap_overdue_sorted = sorted(ap_overdue, key=lambda x: x.get("balance", 0), reverse=True)[:10]

        return {
            "ar": {
                "total_outstanding": ar_report.get("total_outstanding", 0),
                "buckets": ar_report.get("buckets", {}),
                "entry_count": len(ar_all),
                "overdue_count": len(ar_overdue),
            },
            "ap": {
                "total_outstanding": ap_report.get("total_outstanding", 0),
                "buckets": ap_report.get("buckets", {}),
                "entry_count": len(ap_all),
                "overdue_count": len(ap_overdue),
            },
            "top_overdue_ar": ar_overdue_sorted,
            "top_overdue_ap": ap_overdue_sorted,
            "net_position": round(
                ar_report.get("total_outstanding", 0) - ap_report.get("total_outstanding", 0), 2
            ),
        }
    except Exception as e:
        logger.error(f"Subledger summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_subledger():
    """Seed demo AR/AP data into the sub-ledger."""
    try:
        from app.services.subledger import SubledgerManager
        from datetime import timedelta

        mgr = _mgr()
        today = date.today()

        # Only seed if empty
        if mgr.ar.list_all() or mgr.ap.list_all():
            return {"status": "already_seeded", "message": "Sub-ledger already has data"}

        # Seed AR entries across aging buckets
        ar_data = [
            ("Petrocas Energy", 125000, today + timedelta(days=20), today - timedelta(days=10)),
            ("NYX Core Thinker Trading", 89500, today + timedelta(days=5), today - timedelta(days=25)),
            ("Gulf Oil Georgia", 67800, today - timedelta(days=12), today - timedelta(days=42)),
            ("Wissol Petroleum", 45200, today - timedelta(days=35), today - timedelta(days=65)),
            ("Rompetrol Georgia", 34900, today - timedelta(days=55), today - timedelta(days=85)),
            ("Lukoil Georgia", 28700, today - timedelta(days=80), today - timedelta(days=110)),
            ("Sun Petroleum", 52300, today + timedelta(days=30), today),
            ("Alpha Fuel Ltd", 18900, today - timedelta(days=100), today - timedelta(days=130)),
            ("Trans Oil Co", 73400, today - timedelta(days=20), today - timedelta(days=50)),
            ("EnerGeo Supply", 41600, today - timedelta(days=45), today - timedelta(days=75)),
            ("Batumi Terminal", 96200, today + timedelta(days=10), today - timedelta(days=20)),
            ("Poti Port Fuel", 31500, today - timedelta(days=70), today - timedelta(days=100)),
        ]
        for cust, amt, due, issue in ar_data:
            mgr.ar.add_invoice(cust, amt, due, issue_date=issue)

        # Seed AP entries across aging buckets
        ap_data = [
            ("Azpetrol Supply", 98000, today + timedelta(days=25), today - timedelta(days=5)),
            ("Turkish Petroleum", 76500, today + timedelta(days=10), today - timedelta(days=20)),
            ("KazTransOil", 54300, today - timedelta(days=8), today - timedelta(days=38)),
            ("Shell Trading", 43700, today - timedelta(days=32), today - timedelta(days=62)),
            ("BP Logistics", 29800, today - timedelta(days=60), today - timedelta(days=90)),
            ("Total Energies", 67200, today + timedelta(days=15), today - timedelta(days=15)),
            ("Chevron Supply", 22400, today - timedelta(days=95), today - timedelta(days=125)),
            ("Vitol Trading", 85100, today - timedelta(days=15), today - timedelta(days=45)),
            ("Trafigura Co", 38900, today - timedelta(days=50), today - timedelta(days=80)),
            ("Glencore Fuel", 51600, today + timedelta(days=7), today - timedelta(days=23)),
        ]
        for vendor, amt, due, recv in ap_data:
            mgr.ap.add_bill(vendor, amt, due, received_date=recv)

        return {
            "status": "seeded",
            "ar_entries": len(ar_data),
            "ap_entries": len(ap_data),
            "ar_total": mgr.ar.get_aging_report()["total_outstanding"],
            "ap_total": mgr.ap.get_aging_report()["total_outstanding"],
        }
    except Exception as e:
        logger.error(f"Subledger seed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
