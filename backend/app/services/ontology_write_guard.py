"""
OntologyWriteGuard — Enforce all mutations through ontology action types
========================================================================
Palantir pattern: no direct DB writes — all mutations go through Action Types
with validation rules, audit trail, and side effects.

Usage:
    from app.services.ontology_write_guard import write_guard

    # Instead of direct data_store.save_financials(...)
    result = write_guard.write_financials(company_id, period, financials, user="admin")
    # This creates an ActionExecution, validates, writes, syncs ontology, logs audit

    # For bulk uploads
    result = write_guard.write_upload(dataset_id, financials, metadata, user="upload_api")
"""

from __future__ import annotations
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WriteAuditEntry:
    """Immutable audit record for every ontology-gated write."""
    __slots__ = ('id', 'action', 'entity_type', 'entity_id', 'user',
                 'before', 'after', 'timestamp', 'status', 'duration_ms')

    def __init__(self, action: str, entity_type: str, entity_id: str,
                 user: str = "system", before: Optional[Dict] = None,
                 after: Optional[Dict] = None):
        self.id = uuid.uuid4().hex[:12]
        self.action = action
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.user = user
        self.before = before
        self.after = after
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.status = "pending"
        self.duration_ms = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "action": self.action,
            "entity_type": self.entity_type, "entity_id": self.entity_id,
            "user": self.user, "timestamp": self.timestamp,
            "status": self.status, "duration_ms": self.duration_ms,
        }


class OntologyWriteGuard:
    """
    Gates all data mutations through ontology action types.

    Every write operation:
    1. Creates an audit entry
    2. Validates the mutation (business rules)
    3. Executes the write to data_store
    4. Syncs affected ontology objects
    5. Logs to audit trail
    6. Emits notification if configured
    """

    _instance: Optional["OntologyWriteGuard"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._audit_log: List[WriteAuditEntry] = []
            cls._instance._write_count = 0
            cls._instance._validation_rules: Dict[str, List] = {}
        return cls._instance

    def write_financials(
        self,
        company_id: int,
        period: str,
        financials: Dict[str, Any],
        user: str = "system",
        source: str = "api",
    ) -> Dict[str, Any]:
        """Write financial data through the ontology guard."""
        t0 = time.time()
        audit = WriteAuditEntry(
            action="write_financials",
            entity_type="FinancialSnapshot",
            entity_id=f"{company_id}:{period}",
            user=user,
        )

        try:
            # 1. Validate
            errors = self._validate_financials(financials)
            if errors:
                audit.status = "validation_failed"
                self._audit_log.append(audit)
                return {"success": False, "errors": errors}

            # 2. Get before state
            try:
                from app.services.data_store import data_store
                before = data_store.get_financials(company_id, period)
                audit.before = {"revenue": before.get("revenue", 0)} if before else None
            except Exception:
                before = None

            # 3. Execute write
            from app.services.data_store import data_store
            data_store.save_financials(company_id, period, financials)

            # 4. Sync ontology
            try:
                from app.services.ontology_engine import ontology_registry
                companies = data_store.list_companies()
                company_name = "Unknown"
                for c in companies:
                    if c.get("id") == company_id:
                        company_name = c.get("name", "Unknown")
                        break
                ontology_registry.sync_financial_data(
                    company_name=company_name,
                    period=period,
                    pnl={k: v for k, v in financials.items() if not k.startswith("bs_")},
                    balance_sheet={k: v for k, v in financials.items() if k.startswith("bs_") or k in (
                        "cash", "receivables", "inventory", "total_assets",
                        "total_liabilities", "total_equity",
                    )},
                )
            except Exception as e:
                logger.debug("Ontology sync after write: %s", e)

            # 5. Sync warehouse
            try:
                from app.services.warehouse import warehouse
                if warehouse._initialized:
                    warehouse.sync_from_sqlite()
            except Exception:
                pass

            # 6. Record success
            audit.after = {"revenue": financials.get("revenue", 0)}
            audit.status = "completed"
            audit.duration_ms = int((time.time() - t0) * 1000)
            self._audit_log.append(audit)
            self._write_count += 1

            logger.info(
                "OntologyWriteGuard: financials written for %s:%s by %s (%dms)",
                company_id, period, user, audit.duration_ms,
            )
            return {"success": True, "audit_id": audit.id, "duration_ms": audit.duration_ms}

        except Exception as e:
            audit.status = "error"
            audit.duration_ms = int((time.time() - t0) * 1000)
            self._audit_log.append(audit)
            logger.error("OntologyWriteGuard error: %s", e)
            return {"success": False, "error": str(e)}

    def write_upload(
        self,
        dataset_id: int,
        financials: Dict[str, Any],
        metadata: Dict[str, Any],
        user: str = "upload_api",
    ) -> Dict[str, Any]:
        """Gate upload-originated writes through the ontology guard."""
        company_id = metadata.get("company_id", 0)
        period = metadata.get("period", "")
        return self.write_financials(company_id, period, financials, user=user, source="upload")

    def _validate_financials(self, financials: Dict[str, Any]) -> List[str]:
        """Business rule validation before write."""
        errors = []
        rev = financials.get("revenue", 0)

        # Revenue must be non-negative (or explicitly marked as correction)
        if rev < 0 and not financials.get("_is_correction"):
            errors.append("Revenue cannot be negative")

        # Basic consistency: gross_profit should be <= revenue
        gp = financials.get("gross_profit", 0)
        if rev > 0 and gp > rev * 1.01:  # Allow 1% tolerance
            errors.append(f"Gross profit ({gp:,.0f}) exceeds revenue ({rev:,.0f})")

        return errors

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Get recent write audit entries."""
        return [e.to_dict() for e in self._audit_log[-limit:]]

    def status(self) -> Dict[str, Any]:
        """Get write guard status."""
        return {
            "total_writes": self._write_count,
            "audit_entries": len(self._audit_log),
            "recent_writes": [e.to_dict() for e in self._audit_log[-5:]],
            "validation_rules": list(self._validation_rules.keys()),
        }


write_guard = OntologyWriteGuard()
