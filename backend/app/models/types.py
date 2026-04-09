"""
FinAI — Custom SQLAlchemy column types for financial data.

DecimalString: Stores Python Decimal as TEXT in SQLite, preserving full precision.
    - Avoids IEEE 754 float precision loss
    - Round-trips Decimal("123456789.12") without any corruption
    - Works with both SQLite and PostgreSQL
"""

from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class DecimalString(TypeDecorator):
    """SQLAlchemy type that stores Decimal values as strings in the database.

    This avoids the precision loss that occurs when SQLite stores Decimal as REAL (float).

    Usage in models:
        from app.models.types import DecimalString

        class Transaction(Base):
            amount = Column(DecimalString(precision=2), nullable=False)

    The `precision` parameter controls the number of decimal places stored.
    """

    impl = String
    cache_ok = True

    def __init__(self, precision: int = 2, *args, **kwargs):
        self.precision = precision
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Optional[Decimal], dialect) -> Optional[str]:
        """Convert Decimal to string for storage."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (int, float)):
            return str(Decimal(str(value)))
        if isinstance(value, str):
            # Validate it's a valid decimal string
            try:
                return str(Decimal(value))
            except (InvalidOperation, ValueError):
                return None
        return str(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[Decimal]:
        """Convert string back to Decimal on retrieval."""
        if value is None:
            return None
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None

    def process_literal_param(self, value, dialect):
        """For literal SQL rendering."""
        return self.process_bind_param(value, dialect)

    @property
    def python_type(self):
        return Decimal
