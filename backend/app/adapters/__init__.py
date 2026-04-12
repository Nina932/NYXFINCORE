"""
ERP Adapter Framework — Standardized interface for parsing financial data
from any ERP system (1C, QuickBooks, SAP B1, Xero, etc.).

Usage:
    from app.adapters import detect_erp_system, get_adapter

    adapter = detect_erp_system(file_path)
    accounts = adapter.parse_chart_of_accounts(file_path)
    transactions = adapter.parse_transactions(file_path)
"""

from app.adapters.base_adapter import BaseERPAdapter, StandardAccount, StandardTransaction
from app.adapters.registry import detect_erp_system, get_adapter, register_adapter

# Import adapters to trigger @register_adapter decoration
import app.adapters.onec_adapter  # noqa: F401

__all__ = [
    "BaseERPAdapter",
    "StandardAccount",
    "StandardTransaction",
    "detect_erp_system",
    "get_adapter",
    "register_adapter",
]
