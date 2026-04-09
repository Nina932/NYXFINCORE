"""
Test Suite: v2 Journal System — Double-Entry Enforcement, Period Control, Immutability
=======================================================================================
"""
import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.services.v2.journal_system import (
    journal_service, UnbalancedEntryError, PeriodClosedError, ImmutableEntryError,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    from app.database import AsyncSessionLocal, engine, Base
    import asyncio

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return AsyncSessionLocal()

    return asyncio.get_event_loop().run_until_complete(_setup())


class TestJournalServiceSync:
    """Synchronous wrapper tests for journal system validation logic."""

    def test_unbalanced_entry_rejected(self):
        """DR != CR must raise UnbalancedEntryError."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                with pytest.raises(UnbalancedEntryError):
                    await journal_service.create_entry(
                        posting_date=datetime.now(timezone.utc),
                        period="January 2026",
                        fiscal_year=2026,
                        description="Unbalanced test",
                        lines=[
                            {"account_code": "1110", "debit": "100", "credit": "0"},
                            {"account_code": "6110", "debit": "0", "credit": "50"},
                        ],
                        db=db,
                    )
        asyncio.get_event_loop().run_until_complete(_test())

    def test_balanced_entry_accepted(self):
        """DR == CR must succeed."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                result = await journal_service.create_entry(
                    posting_date=datetime.now(timezone.utc),
                    period="January 2026",
                    fiscal_year=2026,
                    description="Balanced test",
                    lines=[
                        {"account_code": "1110", "debit": "1000", "credit": "0"},
                        {"account_code": "6110", "debit": "0", "credit": "1000"},
                    ],
                    db=db,
                )
                await db.commit()
                assert result["status"] == "draft"
                assert result["total_debit"] == "1000.00"
                assert result["total_credit"] == "1000.00"
        asyncio.get_event_loop().run_until_complete(_test())

    def test_post_assigns_document_number(self):
        """Posting must assign a sequential document number."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                je = await journal_service.create_entry(
                    posting_date=datetime.now(timezone.utc),
                    period="January 2026", fiscal_year=2026,
                    description="Post test",
                    lines=[
                        {"account_code": "1110", "debit": "500", "credit": "0"},
                        {"account_code": "2110", "debit": "0", "credit": "500"},
                    ],
                    db=db,
                )
                posted = await journal_service.post_entry(je["id"], db=db)
                await db.commit()
                assert posted["status"] == "posted"
                assert posted["document_number"].startswith("JE-2026-")
                assert posted["is_immutable"] is True
                assert posted["document_hash"] is not None
        asyncio.get_event_loop().run_until_complete(_test())

    def test_zero_amount_rejected(self):
        """All-zero entry must be rejected."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                with pytest.raises(ValueError, match="zero total"):
                    await journal_service.create_entry(
                        posting_date=datetime.now(timezone.utc),
                        period="January 2026", fiscal_year=2026,
                        description="Zero test",
                        lines=[
                            {"account_code": "1110", "debit": "0", "credit": "0"},
                        ],
                        db=db,
                    )
        asyncio.get_event_loop().run_until_complete(_test())

    def test_empty_lines_rejected(self):
        """No lines must be rejected."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                with pytest.raises(ValueError, match="at least one"):
                    await journal_service.create_entry(
                        posting_date=datetime.now(timezone.utc),
                        period="January 2026", fiscal_year=2026,
                        description="Empty test", lines=[], db=db,
                    )
        asyncio.get_event_loop().run_until_complete(_test())

    def test_hash_verification(self):
        """Document hash must match after posting."""
        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                je = await journal_service.create_entry(
                    posting_date=datetime.now(timezone.utc),
                    period="January 2026", fiscal_year=2026,
                    description="Hash test",
                    lines=[
                        {"account_code": "1110", "debit": "999.99", "credit": "0"},
                        {"account_code": "6110", "debit": "0", "credit": "999.99"},
                    ],
                    db=db,
                )
                posted = await journal_service.post_entry(je["id"], db=db)
                await db.commit()

                verify = await journal_service.verify_hash(posted["id"], db)
                assert verify["verified"] is True
                assert verify["tampered"] is False
        asyncio.get_event_loop().run_until_complete(_test())
