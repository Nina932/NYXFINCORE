
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.sql import func
from app.database import Base
from app.models.types import DecimalString

class FactFinancialLedger(Base):
    """
    Consolidated Analytical Fact Table for all financial entries.
    Flattened for institutional reporting (PowerBI / DuckDB).
    """
    __tablename__ = "fact_financial_ledger"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    period           = Column(String(50), index=True)
    
    # Financial Keys
    account_code     = Column(String(50), index=True)
    ifrs_line_item   = Column(String(255), index=True)
    baku_mr_code     = Column(String(50), index=True)
    
    # Dimensions (Normalized)
    business_unit    = Column(String(100), index=True) # Batumi, Tbilisi, etc.
    product_category = Column(String(100), index=True) # Diesel, Petrol, etc.
    counterparty     = Column(String(200), index=True)
    
    # Measurements
    amount_gel       = Column(DecimalString(precision=2), default="0")
    amount_usd       = Column(DecimalString(precision=2), default="0")
    quantity         = Column(Float, default=0.0) # For product movements
    
    # Forensic Meta
    entry_type       = Column(String(50)) # Transaction | BalanceSnapshot | Adjustment
    confidence_score = Column(Float, default=1.0)
    audit_id         = Column(String(100))
    
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("ix_fact_period_unit", "period", "business_unit"),
        Index("ix_fact_acct_period", "account_code", "period"),
    )

class DimProduct(Base):
    """Normalized Product Dimension."""
    __tablename__ = "dim_products"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    product_name  = Column(String(255), unique=True, nullable=False)
    category      = Column(String(100))
    segment       = Column(String(100)) # Wholesale | Retail
    unit_measure  = Column(String(20))
    is_active     = Column(Boolean, default=True)

class DimBusinessUnit(Base):
    """Normalized Business Unit (Department/Location) Dimension."""
    __tablename__ = "dim_business_units"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), unique=True, nullable=False)
    region        = Column(String(50))
    manager       = Column(String(100))
    unit_type     = Column(String(50)) # Retail Outlet | Warehouse | HQ

class TapState(Base):
    """
    Persistence layer for Singer Connector State.
    Enables incremental loading and restartability.
    """
    __tablename__ = "tap_states"
    tap_id        = Column(String(100), primary_key=True)
    state_json    = Column(JSON, nullable=False)
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
