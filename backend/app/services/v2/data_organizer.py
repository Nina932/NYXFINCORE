"""
FinAI Smart Data Organizer
============================
Organizes datasets thematically, by year, by need.
- Auto-groups datasets by period, company, type
- Provides smart recommendations for which dataset to use
- Manages dataset lifecycle (active/archive/delete)
- Tracks dataset quality and usage patterns
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class DataOrganizer:
    """Smart data organization and recommendation engine."""

    async def get_organized_view(self, db) -> Dict[str, Any]:
        """Get all datasets organized by year, type, and quality."""
        from app.models.all_models import Dataset
        from sqlalchemy import select

        result = await db.execute(select(Dataset).where(Dataset.record_count > 0).order_by(Dataset.id.desc()))
        datasets = result.scalars().all()

        # Group by year
        by_year: Dict[str, List[Dict]] = defaultdict(list)
        by_type: Dict[str, List[Dict]] = defaultdict(list)
        by_company: Dict[str, List[Dict]] = defaultdict(list)

        for ds in datasets:
            info = {
                "id": ds.id,
                "name": ds.original_filename or ds.name or f"Dataset {ds.id}",
                "period": ds.period or "Unknown",
                "record_count": ds.record_count,
                "file_type": ds.file_type or "Unknown",
                "company": ds.company or "Unknown",
                "status": ds.status,
                "is_active": ds.is_active,
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
                "quality_tier": self._assess_quality(ds),
                "is_test_data": ds.record_count >= 50000,
            }

            # Extract year from period
            year = self._extract_year(ds.period)
            by_year[year].append(info)
            by_type[ds.file_type or "Unknown"].append(info)
            by_company[ds.company or "Unknown"].append(info)

        # Build recommendations
        recommendations = self._build_recommendations(datasets)

        return {
            "total_datasets": len(datasets),
            "by_year": {k: {"count": len(v), "datasets": v} for k, v in sorted(by_year.items(), reverse=True)},
            "by_type": {k: {"count": len(v), "datasets": v} for k, v in by_type.items()},
            "by_company": {k: {"count": len(v), "datasets": v} for k, v in by_company.items()},
            "recommendations": recommendations,
            "summary": {
                "years_covered": sorted(by_year.keys(), reverse=True),
                "total_records": sum(ds.record_count for ds in datasets),
                "file_types": list(by_type.keys()),
                "companies": [c for c in by_company.keys() if c != "Unknown"],
                "test_data_count": sum(1 for ds in datasets if ds.record_count >= 50000),
                "production_data_count": sum(1 for ds in datasets if ds.record_count < 50000),
            },
        }

    async def get_smart_recommendation(self, db, purpose: str = "analysis") -> Dict[str, Any]:
        """Recommend the best dataset for a specific purpose."""
        from app.models.all_models import Dataset
        from sqlalchemy import select

        result = await db.execute(select(Dataset).where(Dataset.record_count > 0).order_by(Dataset.id.desc()))
        datasets = result.scalars().all()

        # Filter out test data for most purposes
        production = [ds for ds in datasets if ds.record_count < 50000]
        if not production:
            production = datasets

        purpose_lower = purpose.lower()

        if "current" in purpose_lower or "latest" in purpose_lower or "2026" in purpose_lower:
            # Most recent production dataset
            best = production[0] if production else datasets[0]
        elif "prior" in purpose_lower or "comparison" in purpose_lower or "2025" in purpose_lower:
            # Find prior year data
            best = next((ds for ds in production if "2025" in (ds.period or "")), production[-1] if production else datasets[-1])
        elif "full" in purpose_lower or "complete" in purpose_lower:
            # Largest production dataset
            best = max(production, key=lambda d: d.record_count)
        elif "test" in purpose_lower or "stress" in purpose_lower:
            best = next((ds for ds in datasets if ds.record_count >= 50000), datasets[0])
        else:
            best = production[0] if production else datasets[0]

        return {
            "purpose": purpose,
            "recommended": {
                "id": best.id,
                "name": best.original_filename or best.name,
                "period": best.period,
                "record_count": best.record_count,
                "reason": f"Best match for '{purpose}' — {best.record_count} records from {best.period}",
            },
            "alternatives": [
                {"id": ds.id, "name": ds.original_filename or ds.name, "period": ds.period, "records": ds.record_count}
                for ds in production[:5] if ds.id != best.id
            ],
        }

    async def archive_dataset(self, db, dataset_id: int) -> Dict[str, Any]:
        """Mark a dataset as archived (not deleted, just hidden from default views)."""
        from app.models.all_models import Dataset
        from sqlalchemy import select

        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        ds = result.scalar_one_or_none()
        if not ds:
            return {"error": "Dataset not found"}

        ds.is_active = False
        await db.commit()
        return {"id": ds.id, "name": ds.original_filename, "status": "archived"}

    def _extract_year(self, period: str) -> str:
        if not period:
            return "Unknown"
        import re
        match = re.search(r'20\d{2}', period)
        return match.group() if match else "Unknown"

    def _assess_quality(self, ds) -> str:
        if ds.record_count >= 50000:
            return "test"
        if ds.record_count >= 1000:
            return "high"
        if ds.record_count >= 100:
            return "medium"
        return "low"

    def _build_recommendations(self, datasets) -> List[Dict[str, Any]]:
        recs = []

        # Check for test data
        test_data = [ds for ds in datasets if ds.record_count >= 50000]
        if test_data:
            recs.append({
                "type": "cleanup",
                "priority": "low",
                "message": f"{len(test_data)} test dataset(s) found. Consider archiving to keep your workspace clean.",
                "action": "archive_test_data",
                "dataset_ids": [ds.id for ds in test_data],
            })

        # Check for duplicate periods
        period_counts = defaultdict(int)
        for ds in datasets:
            if ds.period:
                period_counts[ds.period] += 1
        duplicates = {p: c for p, c in period_counts.items() if c > 1}
        if duplicates:
            recs.append({
                "type": "dedup",
                "priority": "medium",
                "message": f"Multiple datasets for same period: {', '.join(f'{p} ({c} files)' for p, c in duplicates.items())}",
                "action": "review_duplicates",
            })

        # Check for missing periods (gaps)
        years = set()
        for ds in datasets:
            import re
            match = re.search(r'20(\d{2})', ds.period or "")
            if match:
                years.add(int(f"20{match.group(1)}"))
        if len(years) > 1:
            min_year, max_year = min(years), max(years)
            missing = [y for y in range(min_year, max_year + 1) if y not in years]
            if missing:
                recs.append({
                    "type": "coverage",
                    "priority": "info",
                    "message": f"Missing data for years: {', '.join(str(y) for y in missing)}",
                    "action": "upload_missing",
                })

        return recs


# Global instance
data_organizer = DataOrganizer()
