"""
FinAI Database Models — matches frontend v6 data model exactly
Field names aligned with frontend SEED_DATA and parseFile output
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.types import DecimalString
import enum


def _default_company():
    """Dynamic company name default — reads from settings at row-creation time."""
    try:
        from app.config import settings
        return settings.COMPANY_NAME
    except Exception:
        return "NYX Core Thinker LLC"


class Dataset(Base):
    __tablename__ = "datasets"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(255), nullable=False)
    original_filename= Column(String(255))
    file_type        = Column(String(100), default="Financial Data")
    file_size        = Column(Integer, default=0)
    extension        = Column(String(10))
    sheet_count      = Column(Integer, default=1)
    record_count     = Column(Integer, default=0)
    status           = Column(String(20), default="ready")
    is_seed          = Column(Boolean, default=False)
    data_source      = Column(String(20), default="real")   # real | seed | synthetic | fallback
    is_active        = Column(Boolean, default=False)
    period           = Column(String(50), default="January 2025")
    currency         = Column(String(10), default="GEL")
    company          = Column(String(100), default=_default_company)
    upload_path      = Column(String(500))
    group_id         = Column(Integer, ForeignKey("dataset_groups.id", ondelete="SET NULL"), nullable=True)
    parse_error      = Column(Text)
    parse_metadata   = Column(JSON)    # Processing pipeline, sheet detection, coverage stats
    owner_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Phase G-4
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())
    transactions     = relationship("Transaction", back_populates="dataset", cascade="all, delete-orphan")
    revenue_items    = relationship("RevenueItem", back_populates="dataset", cascade="all, delete-orphan")
    budget_lines     = relationship("BudgetLine", back_populates="dataset", cascade="all, delete-orphan")
    cogs_items       = relationship("COGSItem", back_populates="dataset", cascade="all, delete-orphan")
    ga_expense_items = relationship("GAExpenseItem", back_populates="dataset", cascade="all, delete-orphan")
    balance_sheet_items = relationship("BalanceSheetItem", back_populates="dataset", cascade="all, delete-orphan")
    trial_balance_items = relationship("TrialBalanceItem", back_populates="dataset", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_dataset_created","created_at"), Index("ix_dataset_active","is_active"), Index("ix_dataset_period","period"),)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"original_filename":self.original_filename,"file_type":self.file_type,"file_size":self.file_size,"extension":self.extension,"record_count":self.record_count,"status":self.status,"is_seed":self.is_seed,"data_source":self.data_source or ("seed" if self.is_seed else "real"),"is_active":self.is_active,"period":self.period,"currency":self.currency,"company":self.company,"sheet_count":self.sheet_count,"parse_metadata":self.parse_metadata,"created_at":self.created_at.isoformat() if self.created_at else None,"updated_at":self.updated_at.isoformat() if self.updated_at else None}


class DatasetSnapshot(Base):
    """Immutable dataset snapshot for versioning and duplicate detection."""
    __tablename__ = "dataset_snapshots"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id    = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    version       = Column(Integer, default=1)
    fingerprint   = Column(String(128), nullable=False)
    record_counts = Column(JSON)
    totals_json   = Column(JSON)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_snapshot_dataset","dataset_id"),
        Index("ix_snapshot_fingerprint","fingerprint"),
    )
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"version":self.version,"fingerprint":self.fingerprint,"record_counts":self.record_counts,"totals_json":self.totals_json,"created_at":self.created_at.isoformat() if self.created_at else None}


class SchemaProfile(Base):
    """Schema profile for a specific file type / business unit."""
    __tablename__ = "schema_profiles"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False)
    file_type    = Column(String(100), default="generic")
    business_unit= Column(String(100))
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_schema_profile_active","is_active"), Index("ix_schema_profile_type","file_type"),)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"file_type":self.file_type,"business_unit":self.business_unit,"is_active":self.is_active,"created_at":self.created_at.isoformat() if self.created_at else None}


class SchemaVersion(Base):
    """Versioned schema rules (JSON) tied to a profile."""
    __tablename__ = "schema_versions"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("schema_profiles.id", ondelete="CASCADE"), nullable=False)
    version    = Column(Integer, default=1)
    rules_json = Column(JSON)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_schema_version_profile","profile_id"), Index("ix_schema_version_active","is_active"),)
    def to_dict(self):
        return {"id":self.id,"profile_id":self.profile_id,"version":self.version,"rules_json":self.rules_json,"is_active":self.is_active,"created_at":self.created_at.isoformat() if self.created_at else None}


class SchemaProposal(Base):
    """Proposed schema when a file doesn't match any active profile."""
    __tablename__ = "schema_proposals"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    file_name           = Column(String(255), nullable=False)
    sheet_names         = Column(JSON)
    header_samples      = Column(JSON)
    suggested_rules_json= Column(JSON)
    status              = Column(String(20), default="pending")  # pending|approved|rejected
    approved_profile_id = Column(Integer, ForeignKey("schema_profiles.id", ondelete="SET NULL"), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_schema_proposal_status","status"),)
    def to_dict(self):
        return {"id":self.id,"file_name":self.file_name,"sheet_names":self.sheet_names,"header_samples":self.header_samples,"suggested_rules_json":self.suggested_rules_json,"status":self.status,"approved_profile_id":self.approved_profile_id,"created_at":self.created_at.isoformat() if self.created_at else None}


class ETLAuditEvent(Base):
    """Step-by-step ETL audit trail for deterministic ingestion."""
    __tablename__ = "etl_audit_events"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id   = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    step         = Column(String(100), nullable=False)
    status       = Column(String(20), default="ok")  # ok|warn|error
    detail       = Column(Text)
    metadata_json= Column(JSON)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_etl_dataset","dataset_id"), Index("ix_etl_step","step"), Index("ix_etl_created","created_at"),)
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"step":self.step,"status":self.status,"detail":self.detail,"metadata_json":self.metadata_json,"created_at":self.created_at.isoformat() if self.created_at else None}


class Transaction(Base):
    """Field names match frontend parseFile output exactly: date, recorder, acct_dr, acct_cr, dept, counterparty, cost_class, type, amount, vat"""
    __tablename__ = "transactions"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id   = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    date         = Column(String(20))
    recorder     = Column(String(255))
    acct_dr      = Column(String(50))
    acct_cr      = Column(String(50))
    dept         = Column(String(100))
    counterparty = Column(String(200))
    cost_class   = Column(String(100))
    type         = Column(String(20), default="Expense")   # Expense | Income | Transfer
    amount       = Column(DecimalString(precision=2), default="0")
    vat          = Column(DecimalString(precision=2), default="0")
    currency     = Column(String(10), default="GEL")
    period       = Column(String(50))
    data_source  = Column(String(20), default="real")   # real | seed | synthetic
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    dataset      = relationship("Dataset", back_populates="transactions")
    __table_args__ = (Index("ix_txn_dataset","dataset_id"), Index("ix_txn_type","type"), Index("ix_txn_dept","dept"), Index("ix_txn_date","date"), Index("ix_txn_cost_class","cost_class"), Index("ix_txn_counterparty","counterparty"),)
    def to_dict(self):
        return {"id":self.id,"date":self.date,"recorder":self.recorder,"acct_dr":self.acct_dr,"acct_cr":self.acct_cr,"dept":self.dept,"counterparty":self.counterparty,"cost_class":self.cost_class,"type":self.type,"amount":float(self.amount) if self.amount else 0,"vat":float(self.vat) if self.vat else 0,"currency":self.currency,"data_source":self.data_source or "real"}


class RevenueItem(Base):
    """Field names match frontend: product, gross, vat, net, segment"""
    __tablename__ = "revenue_items"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    product    = Column(String(255), nullable=False)
    gross      = Column(DecimalString(precision=2), default="0")
    vat        = Column(DecimalString(precision=2), default="0")
    net        = Column(DecimalString(precision=2), default="0")
    segment    = Column(String(100), default="Other Revenue")
    category   = Column(String(100))  # "Revenue Whsale Petrol", "Revenue Retial CNG", etc.
    eliminated  = Column(Boolean, default=False)  # Intercompany elimination flag from Excel
    currency    = Column(String(10), default="GEL")
    period      = Column(String(50))
    data_source = Column(String(20), default="real")   # real | seed | synthetic
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    dataset     = relationship("Dataset", back_populates="revenue_items")
    __table_args__ = (Index("ix_rev_dataset","dataset_id"), Index("ix_rev_segment","segment"),)
    def to_dict(self):
        return {"id":self.id,"product":self.product,"gross":float(self.gross) if self.gross else 0,"vat":float(self.vat) if self.vat else 0,"net":float(self.net) if self.net else 0,"segment":self.segment,"category":self.category,"eliminated":self.eliminated,"data_source":self.data_source or "real"}


class COGSItem(Base):
    """Parsed COGS Breakdown data — one row per product per period."""
    __tablename__ = "cogs_items"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id     = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    product        = Column(String(255), nullable=False)
    col6_amount    = Column(DecimalString(precision=2), default="0")    # Column K (account 6)
    col7310_amount = Column(DecimalString(precision=2), default="0")    # Column L (account 7310)
    col8230_amount = Column(DecimalString(precision=2), default="0")    # Column O (account 8230)
    total_cogs     = Column(DecimalString(precision=2), default="0")    # K + L + O
    segment        = Column(String(100), default="Other COGS")   # "COGS Wholesale" | "COGS Retail" | "Other COGS"
    category       = Column(String(100))           # "COGS Whsale Petrol", "COGS Retial Diesel", etc.
    currency       = Column(String(10), default="GEL")
    period         = Column(String(50))
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    dataset        = relationship("Dataset", back_populates="cogs_items")
    __table_args__ = (Index("ix_cogs_dataset","dataset_id"), Index("ix_cogs_segment","segment"), Index("ix_cogs_category","category"),)
    def to_dict(self):
        return {"id":self.id,"product":self.product,"col6":float(self.col6_amount) if self.col6_amount else 0,"col7310":float(self.col7310_amount) if self.col7310_amount else 0,"col8230":float(self.col8230_amount) if self.col8230_amount else 0,"total_cogs":float(self.total_cogs) if self.total_cogs else 0,"segment":self.segment,"category":self.category}


class GAExpenseItem(Base):
    """G&A Expense items extracted from Base sheet by account code."""
    __tablename__ = "ga_expense_items"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id    = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    account_code  = Column(String(50), nullable=False)
    account_name  = Column(String(255))
    amount        = Column(DecimalString(precision=2), default="0")
    currency      = Column(String(10), default="GEL")
    period        = Column(String(50))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    dataset       = relationship("Dataset", back_populates="ga_expense_items")
    __table_args__ = (Index("ix_ga_dataset","dataset_id"), Index("ix_ga_account","account_code"),)
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"account_name":self.account_name,"amount":float(self.amount) if self.amount else 0}


class BalanceSheetItem(Base):
    """Parsed Balance sheet rows with IFRS MAPPING GRP classification."""
    __tablename__ = "balance_sheet_items"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    account_code     = Column(String(50))
    account_name     = Column(String(500))
    ifrs_line_item   = Column(String(255))       # MAPPING GRP: "Cash and cash equivalents", "Trade receivables", etc.
    ifrs_statement   = Column(String(10))         # "BS" or "IS"
    baku_bs_mapping  = Column(String(255))       # MAPING BAKU (BS): MR report line mapping
    intercompany_entity = Column(String(100))    # Intercompany entity flag: "SGG", "SEG", etc.
    opening_balance  = Column(DecimalString(precision=2), default="0")
    turnover_debit   = Column(DecimalString(precision=2), default="0")
    turnover_credit  = Column(DecimalString(precision=2), default="0")
    closing_balance  = Column(DecimalString(precision=2), default="0")
    row_type         = Column(String(50))         # "სხვა" (summary) or "საქვეანგარიშგებო" (detail)
    currency         = Column(String(10), default="GEL")
    period           = Column(String(50))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    dataset          = relationship("Dataset", back_populates="balance_sheet_items")
    __table_args__   = (Index("ix_bsi_dataset","dataset_id"), Index("ix_bsi_ifrs","ifrs_line_item"), Index("ix_bsi_stmt","ifrs_statement"),)
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"account_name":self.account_name,"ifrs_line_item":self.ifrs_line_item,"ifrs_statement":self.ifrs_statement,"baku_bs_mapping":self.baku_bs_mapping,"intercompany_entity":self.intercompany_entity,"opening_balance":float(self.opening_balance) if self.opening_balance else 0,"turnover_debit":float(self.turnover_debit) if self.turnover_debit else 0,"turnover_credit":float(self.turnover_credit) if self.turnover_credit else 0,"closing_balance":float(self.closing_balance) if self.closing_balance else 0,"row_type":self.row_type}


class TrialBalanceItem(Base):
    """Parsed TDSheet (Trial Balance) rows — account-level turnovers."""
    __tablename__ = "trial_balance_items"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id        = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    account_code      = Column(String(50))
    account_name      = Column(String(500))
    sub_account_detail= Column(String(500))
    opening_debit     = Column(DecimalString(precision=2), default="0")
    opening_credit    = Column(DecimalString(precision=2), default="0")
    turnover_debit    = Column(DecimalString(precision=2), default="0")
    turnover_credit   = Column(DecimalString(precision=2), default="0")
    closing_debit     = Column(DecimalString(precision=2), default="0")
    closing_credit    = Column(DecimalString(precision=2), default="0")
    net_pl_impact     = Column(DecimalString(precision=2), default="0")   # Column T: Debit - Credit for P&L accounts
    account_class     = Column(String(10))            # First digit: 1-9
    hierarchy_level   = Column(Integer, default=1)    # 1=parent, 2=sub-account, 3=detail
    mr_mapping        = Column(String(50))            # Baku MR code inherited from COA (e.g. "10.B.03.01")
    mr_mapping_line   = Column(String(255))           # Baku MR line name (e.g. "Cash")
    ifrs_line_item    = Column(String(255))           # IFRS MAPPING GRP inherited from COA
    currency          = Column(String(10), default="GEL")
    period            = Column(String(50))
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    dataset           = relationship("Dataset", back_populates="trial_balance_items")
    __table_args__    = (Index("ix_tb_dataset","dataset_id"), Index("ix_tb_account","account_code"), Index("ix_tb_class","account_class"),)
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"account_name":self.account_name,"sub_account_detail":self.sub_account_detail,"opening_debit":float(self.opening_debit) if self.opening_debit else 0,"opening_credit":float(self.opening_credit) if self.opening_credit else 0,"turnover_debit":float(self.turnover_debit) if self.turnover_debit else 0,"turnover_credit":float(self.turnover_credit) if self.turnover_credit else 0,"closing_debit":float(self.closing_debit) if self.closing_debit else 0,"closing_credit":float(self.closing_credit) if self.closing_credit else 0,"net_pl_impact":float(self.net_pl_impact) if self.net_pl_impact else 0,"account_class":self.account_class,"hierarchy_level":self.hierarchy_level,"mr_mapping":self.mr_mapping,"mr_mapping_line":self.mr_mapping_line,"ifrs_line_item":self.ifrs_line_item}


class BudgetLine(Base):
    """Key-value budget pairs matching frontend BUD dict"""
    __tablename__ = "budget_lines"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id    = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    line_item     = Column(String(200), nullable=False)
    budget_amount = Column(DecimalString(precision=2), default="0")
    actual_amount = Column(DecimalString(precision=2))
    currency      = Column(String(10), default="GEL")
    period        = Column(String(50))
    category      = Column(String(50))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    dataset       = relationship("Dataset", back_populates="budget_lines")
    __table_args__ = (Index("ix_bud_dataset","dataset_id"), Index("ix_bud_period","period"),)
    def to_dict(self):
        return {"line_item":self.line_item,"amount":float(self.actual_amount) if self.actual_amount is not None else (float(self.budget_amount) if self.budget_amount else 0)}


class Report(Base):
    """Saved reports — rows use frontend format: {c,l,ac,pl,lvl,bold,sep,s}"""
    __tablename__ = "reports"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    title             = Column(String(255), nullable=False)
    report_type       = Column(String(20), nullable=False)
    period            = Column(String(50), default="January 2025")
    currency          = Column(String(10), default="GEL")
    company           = Column(String(100), default=_default_company)
    status            = Column(String(20), default="ready")
    rows              = Column(JSON)       # [{c,l,ac,pl,lvl,bold,sep,s}]
    summary           = Column(Text)
    kpis              = Column(JSON)       # {revenue,gross_margin,ebitda,net_profit}
    metadata_json     = Column(JSON)
    generated_by      = Column(String(50), default="user")
    source_dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    export_path       = Column(String(500))
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__    = (Index("ix_report_type","report_type"), Index("ix_report_period","period"), Index("ix_report_created","created_at"),)
    def to_dict(self):
        return {"id":self.id,"title":self.title,"report_type":self.report_type,"period":self.period,"currency":self.currency,"rows":self.rows,"summary":self.summary,"kpis":self.kpis,"generated_by":self.generated_by,"status":self.status,"created_at":self.created_at.isoformat() if self.created_at else None}


class ProductMapping(Base):
    """User-approved product-to-category mappings for unmapped products."""
    __tablename__ = "product_mappings"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    product_name     = Column(String(255), unique=True, nullable=False)
    product_name_en  = Column(String(255))
    revenue_category = Column(String(100))
    cogs_category    = Column(String(100))
    is_approved      = Column(Boolean, default=False)
    suggested_by     = Column(String(20), default="system")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    def to_dict(self):
        return {"id":self.id,"product_name":self.product_name,"product_name_en":self.product_name_en,"revenue_category":self.revenue_category,"cogs_category":self.cogs_category,"is_approved":self.is_approved,"suggested_by":self.suggested_by}


class COAMappingOverride(Base):
    """User-editable COA mapping overrides — one per account code, persists across uploads."""
    __tablename__ = "coa_mapping_overrides"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    account_code    = Column(String(50), unique=True, nullable=False)
    account_name    = Column(String(500))
    ifrs_line_item  = Column(String(255), nullable=False)  # e.g. "Cash & Equivalents"
    bs_side         = Column(String(20))    # asset|liability|equity|income|expense
    bs_sub          = Column(String(20))    # current|noncurrent|equity
    pl_line         = Column(String(100))   # COGS|SGA|DA|Finance|Tax (for P&L accounts)
    created_by      = Column(String(100), default="user")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__  = (Index("ix_coa_override_code", "account_code"),)
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"account_name":self.account_name,"ifrs_line_item":self.ifrs_line_item,"bs_side":self.bs_side,"bs_sub":self.bs_sub,"pl_line":self.pl_line,"created_by":self.created_by,"created_at":self.created_at.isoformat() if self.created_at else None}


class COAMasterAccount(Base):
    """Master Chart of Accounts from 1C ანგარიშები.xlsx — 406 accounts with rich metadata."""
    __tablename__ = "coa_master_accounts"
    id                      = Column(Integer, primary_key=True, autoincrement=True)
    account_code            = Column(String(50), unique=True, nullable=False)
    account_code_normalized = Column(String(50), index=True)
    account_prefix          = Column(String(10), index=True)
    name_ka                 = Column(String(500))
    name_ru                 = Column(String(500))
    account_type            = Column(String(5))
    account_type_en         = Column(String(20))
    is_off_balance          = Column(Boolean, default=False)
    tracks_currency         = Column(Boolean, default=False)
    tracks_quantity         = Column(Boolean, default=False)
    subconto_1              = Column(String(200))
    subconto_2              = Column(String(200))
    subconto_3              = Column(String(200))
    ifrs_bs_line            = Column(String(255))
    ifrs_pl_line            = Column(String(255))
    ifrs_side               = Column(String(20))
    ifrs_sub                = Column(String(20))
    ifrs_pl_category        = Column(String(50))
    is_contra               = Column(Boolean, default=False)
    baku_mr_code            = Column(String(50))            # Baku MR report line code (e.g. "10.B.03.01", "02.A")
    baku_mr_line            = Column(String(255))           # Baku MR report line name (e.g. "Cash", "Cost of sales")
    baku_mr_statement       = Column(String(10))            # "BS" or "PL" — which MR statement this maps to
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__          = (Index("ix_coa_master_code", "account_code"), Index("ix_coa_master_norm", "account_code_normalized"), Index("ix_coa_master_prefix", "account_prefix"),)
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"account_code_normalized":self.account_code_normalized,"account_prefix":self.account_prefix,"name_ka":self.name_ka,"name_ru":self.name_ru,"account_type":self.account_type,"account_type_en":self.account_type_en,"is_off_balance":self.is_off_balance,"tracks_currency":self.tracks_currency,"tracks_quantity":self.tracks_quantity,"subconto_1":self.subconto_1,"subconto_2":self.subconto_2,"subconto_3":self.subconto_3,"ifrs_bs_line":self.ifrs_bs_line,"ifrs_pl_line":self.ifrs_pl_line,"ifrs_side":self.ifrs_side,"ifrs_sub":self.ifrs_sub,"ifrs_pl_category":self.ifrs_pl_category,"is_contra":self.is_contra,"baku_mr_code":self.baku_mr_code,"baku_mr_line":self.baku_mr_line,"baku_mr_statement":self.baku_mr_statement,"created_at":self.created_at.isoformat() if self.created_at else None}


class AgentMemory(Base):
    __tablename__ = "agent_memory"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(50), default="conversation")
    content     = Column(Text, nullable=False)
    context     = Column(JSON)
    importance  = Column(Integer, default=5)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_mem_type","memory_type"), Index("ix_mem_active","is_active"),)


# ═══════════════════════════════════════════════════════════════
# MULTI-AGENT ARCHITECTURE MODELS
# ═══════════════════════════════════════════════════════════════

class DatasetGroup(Base):
    """Groups of datasets for multi-period/consolidation analysis.

    Enables cross-period views (Q1 = Jan + Feb + Mar datasets),
    consolidation across subsidiaries, or multi-file processing.
    """
    __tablename__ = "dataset_groups"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text)
    group_type  = Column(String(50), default="period")        # period|consolidation|comparison|custom
    is_active   = Column(Boolean, default=True)
    company     = Column(String(100), default=_default_company, index=True)
    metadata_json = Column(JSON)                               # Flexible metadata
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (Index("ix_dsgroup_active","is_active"), Index("ix_dsgroup_type","group_type"),)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"description":self.description,"group_type":self.group_type,"is_active":self.is_active,"metadata_json":self.metadata_json,"created_at":self.created_at.isoformat() if self.created_at else None}


class AgentAuditLog(Base):
    """Audit trail for multi-agent system — tracks every agent action.

    Compliance-grade logging: who did what, when, with what data, how long,
    how many tokens. Enables the /api/agents/audit monitoring endpoint.
    """
    __tablename__ = "agent_audit_log"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(String(100))                       # Chat session / request ID
    agent_name      = Column(String(50), nullable=False)        # "supervisor"|"calc"|"data"|"insight"|"report"
    action          = Column(String(100), nullable=False)       # "route_task"|"call_tool"|"call_llm"|"error"
    task_type       = Column(String(50))                        # "calculate"|"ingest"|"analyze"|"report"|"chat"
    task_id         = Column(String(50))                        # AgentTask.task_id
    parent_task_id  = Column(String(50))                        # For sub-task chains
    input_summary   = Column(Text)                              # Truncated input description
    output_summary  = Column(Text)                              # Truncated output description
    tool_name       = Column(String(100))                       # Which tool was called (if any)
    status          = Column(String(20), default="success")     # success|error|partial|timeout
    error_message   = Column(Text)
    tokens_input    = Column(Integer, default=0)
    tokens_output   = Column(Integer, default=0)
    duration_ms     = Column(Integer, default=0)
    dataset_id      = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    metadata_json   = Column(JSON)                              # Extra context
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__  = (
        Index("ix_audit_agent","agent_name"),
        Index("ix_audit_session","session_id"),
        Index("ix_audit_action","action"),
        Index("ix_audit_created","created_at"),
        Index("ix_audit_status","status"),
    )
    def to_dict(self):
        return {"id":self.id,"session_id":self.session_id,"agent_name":self.agent_name,"action":self.action,"task_type":self.task_type,"task_id":self.task_id,"tool_name":self.tool_name,"status":self.status,"error_message":self.error_message,"tokens_input":self.tokens_input,"tokens_output":self.tokens_output,"duration_ms":self.duration_ms,"dataset_id":self.dataset_id,"created_at":self.created_at.isoformat() if self.created_at else None}


class Feedback(Base):
    __tablename__ = "feedback"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    feedback_type   = Column(String(20), nullable=False)
    message_content = Column(Text)
    user_question   = Column(Text)
    correction_text = Column(Text)
    session_id      = Column(String(100))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_fb_type","feedback_type"), Index("ix_fb_created","created_at"),)


class CustomTool(Base):
    """User-defined tools — synced with frontend CUSTOM_TOOLS"""
    __tablename__ = "custom_tools"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(100), unique=True, nullable=False)
    description  = Column(Text, nullable=False)
    code         = Column(Text, nullable=False)
    input_schema = Column(JSON)
    is_active    = Column(Boolean, default=True)
    company      = Column(String(100), default=_default_company, index=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())
    def to_dict(self):
        return {"id":self.id,"name":self.name,"description":self.description,"code":self.code,"input_schema":self.input_schema,"is_active":self.is_active,"created_at":self.created_at.isoformat() if self.created_at else None}


# ═══════════════════════════════════════════════════════════════
# ADVANCED FEATURE MODELS
# ═══════════════════════════════════════════════════════════════

class Forecast(Base):
    """Financial forecasts with confidence intervals."""
    __tablename__ = "forecasts"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id          = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    forecast_type       = Column(String(50), nullable=False)    # revenue|cogs|margin|expense|ebitda
    company             = Column(String(100), default=_default_company, index=True)
    product             = Column(String(255))
    segment             = Column(String(100))                    # Wholesale|Retail|Other
    category            = Column(String(100))
    method              = Column(String(50), nullable=False)     # moving_avg|exp_smoothing|linear_regression|growth_rate
    period_start        = Column(String(50))
    period_end          = Column(String(50))
    periods             = Column(Integer, default=6)
    values              = Column(JSON)                           # [{"period","value","lower","upper"}]
    confidence_interval = Column(Float, default=0.95)
    parameters          = Column(JSON)                           # method params {window, alpha, degree, growth_rate}
    input_data          = Column(JSON)                           # historical points used
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__      = (Index("ix_forecast_type","forecast_type"), Index("ix_forecast_dataset","dataset_id"),)
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"forecast_type":self.forecast_type,"product":self.product,"segment":self.segment,"category":self.category,"method":self.method,"period_start":self.period_start,"period_end":self.period_end,"periods":self.periods,"values":self.values,"confidence_interval":self.confidence_interval,"parameters":self.parameters,"created_at":self.created_at.isoformat() if self.created_at else None}


class Scenario(Base):
    """What-if scenarios for financial modeling."""
    __tablename__ = "scenarios"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String(255), nullable=False)
    description     = Column(Text)
    company         = Column(String(100), default=_default_company, index=True)
    base_dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    parameters      = Column(JSON, nullable=False)               # {"changes": [{"target","type","value"}]}
    results         = Column(JSON)                               # computed results {revenue,cogs,margin,ebitda,delta}
    base_snapshot   = Column(JSON)                               # snapshot of base IS values
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__  = (Index("ix_scenario_dataset","base_dataset_id"),)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"description":self.description,"base_dataset_id":self.base_dataset_id,"parameters":self.parameters,"results":self.results,"base_snapshot":self.base_snapshot,"is_active":self.is_active,"created_at":self.created_at.isoformat() if self.created_at else None}


class Anomaly(Base):
    """Detected statistical anomalies in financial data."""
    __tablename__ = "anomalies"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    transaction_id   = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    anomaly_type     = Column(String(50), nullable=False)        # zscore|iqr|benford|seasonal
    company          = Column(String(100), default=_default_company, index=True)
    severity         = Column(String(20), default="medium")      # low|medium|high|critical
    score            = Column(Float, default=0.0)
    description      = Column(Text)
    details          = Column(JSON)
    is_acknowledged  = Column(Boolean, default=False)
    acknowledged_by  = Column(String(100))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (Index("ix_anomaly_dataset","dataset_id"), Index("ix_anomaly_type","anomaly_type"), Index("ix_anomaly_severity","severity"),)
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"transaction_id":self.transaction_id,"anomaly_type":self.anomaly_type,"severity":self.severity,"score":round(self.score,3),"description":self.description,"details":self.details,"is_acknowledged":self.is_acknowledged,"created_at":self.created_at.isoformat() if self.created_at else None}


class ExchangeRate(Base):
    """Historical exchange rates for multi-currency support."""
    __tablename__ = "exchange_rates"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    from_currency  = Column(String(10), nullable=False)
    to_currency    = Column(String(10), nullable=False)
    rate           = Column(DecimalString(precision=6), nullable=False)
    rate_date      = Column(String(20), nullable=False)          # 2025-01-15
    source         = Column(String(100), default="nbg.gov.ge")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_exrate_pair","from_currency","to_currency"), Index("ix_exrate_date","rate_date"),)
    def to_dict(self):
        return {"id":self.id,"from_currency":self.from_currency,"to_currency":self.to_currency,"rate":float(self.rate) if self.rate else 0,"rate_date":self.rate_date,"source":self.source,"created_at":self.created_at.isoformat() if self.created_at else None}


class MRReportSnapshot(Base):
    """Versioned MR report snapshots with USD conversion."""
    __tablename__ = "mr_report_snapshots"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id      = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    report_id       = Column(Integer, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    period          = Column(String(50), nullable=False)
    exchange_rate   = Column(DecimalString(precision=6), nullable=False)
    rate_date       = Column(String(20))
    currency        = Column(String(10), default="USD")
    sections        = Column(JSON)              # {bs:{}, pl:{}, revenue:{}, cogs:{}, opex:{}, ...}
    generated_by    = Column(String(50), default="user")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__  = (Index("ix_mrsnapshot_period","period"), Index("ix_mrsnapshot_ds","dataset_id"),)
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"report_id":self.report_id,"period":self.period,"exchange_rate":float(self.exchange_rate) if self.exchange_rate else 0,"rate_date":self.rate_date,"currency":self.currency,"sections":self.sections,"generated_by":self.generated_by,"created_at":self.created_at.isoformat() if self.created_at else None}


class ScheduledReport(Base):
    """Scheduled report generation and email delivery."""
    __tablename__ = "scheduled_reports"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(255), nullable=False)
    report_type   = Column(String(50), nullable=False)           # pl|bs|mr|is|dashboard
    company       = Column(String(100), default=_default_company, index=True)
    frequency     = Column(String(20), nullable=False)           # daily|weekly|monthly
    recipients    = Column(JSON, nullable=False)                 # ["email1@co.ge"]
    smtp_config   = Column(JSON)                                 # override or None
    parameters    = Column(JSON)                                 # {period, currency, dataset_id}
    next_run      = Column(DateTime(timezone=True))
    last_run      = Column(DateTime(timezone=True))
    last_status   = Column(String(50))                           # success|failed|pending
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_sched_active","is_active"), Index("ix_sched_next","next_run"),)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"report_type":self.report_type,"frequency":self.frequency,"recipients":self.recipients,"parameters":self.parameters,"next_run":self.next_run.isoformat() if self.next_run else None,"last_run":self.last_run.isoformat() if self.last_run else None,"last_status":self.last_status,"is_active":self.is_active,"created_at":self.created_at.isoformat() if self.created_at else None}


class DataLineage(Base):
    """Data origin tracking for every financial figure."""
    __tablename__ = "data_lineage"
    id                        = Column(Integer, primary_key=True, autoincrement=True)
    entity_type               = Column(String(50), nullable=False)  # transaction|revenue_item|cogs_item|ga_expense|budget_line
    entity_id                 = Column(Integer, nullable=False)
    dataset_id                = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True)
    source_file               = Column(String(500))
    source_sheet              = Column(String(100))
    source_row                = Column(Integer)
    source_column             = Column(String(50))
    classification_rule       = Column(String(200))                 # COA:7310.02.1 | Product:Revenue Whsale Petrol
    classification_confidence = Column(Float, default=1.0)
    transform_chain           = Column(JSON)                        # [{"step":"parse","detail":"..."},{"step":"classify",...}]
    uploaded_by               = Column(String(100), default="user")
    created_at                = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__            = (Index("ix_lineage_entity","entity_type","entity_id"), Index("ix_lineage_dataset","dataset_id"),)
    def to_dict(self):
        return {"id":self.id,"entity_type":self.entity_type,"entity_id":self.entity_id,"dataset_id":self.dataset_id,"source_file":self.source_file,"source_sheet":self.source_sheet,"source_row":self.source_row,"source_column":self.source_column,"classification_rule":self.classification_rule,"classification_confidence":self.classification_confidence,"transform_chain":self.transform_chain,"created_at":self.created_at.isoformat() if self.created_at else None}


class User(Base):
    """
    Application user for authentication and multi-tenancy.

    Roles:
      admin   — full access, can manage users
      analyst — standard access (datasets, reports, agent chat)
      viewer  — read-only access
    """
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    username        = Column(String(100), unique=True, nullable=False)
    full_name       = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(20), default="analyst")        # admin|analyst|viewer
    company         = Column(String(100), default=_default_company)
    is_active       = Column(Boolean, default=True)
    is_verified     = Column(Boolean, default=False)
    last_login_at   = Column(DateTime(timezone=True))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__  = (Index("ix_user_email", "email"), Index("ix_user_active", "is_active"),)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "company": self.company,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# PHASE G MODELS
# ═══════════════════════════════════════════════════════════════

class LearningRecord(Base):
    """Persistent learning records for classification improvement (Phase G-2)."""
    __tablename__ = "learning_records"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    account_code      = Column(String(50), nullable=False, index=True)
    classification    = Column(JSON, nullable=False)
    confidence        = Column(Float, default=0.0)
    source            = Column(String(50), default="auto")  # auto|user|llm
    feedback_type     = Column(String(20), default="auto")
    is_active         = Column(Boolean, default=True)
    applied_to_kg     = Column(Boolean, default=False)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__    = (
        Index("ix_learning_code", "account_code"),
        Index("ix_learning_active", "is_active"),
    )
    def to_dict(self):
        return {"id":self.id,"account_code":self.account_code,"classification":self.classification,"confidence":self.confidence,"source":self.source,"feedback_type":self.feedback_type,"is_active":self.is_active,"applied_to_kg":self.applied_to_kg,"created_at":self.created_at.isoformat() if self.created_at else None}


class ClassificationApproval(Base):
    """Pending account classification approvals for user review."""
    __tablename__ = "classification_approvals"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id          = Column(Integer, nullable=True)
    account_code        = Column(String(50), nullable=False)
    account_name        = Column(String(500))
    suggested_section   = Column(String(50))       # income_statement / balance_sheet
    suggested_pl_line   = Column(String(50))       # revenue, cogs, selling_expenses...
    suggested_bs_side   = Column(String(50))       # asset, liability, equity
    suggested_sub       = Column(String(50))       # current, noncurrent
    confidence          = Column(Float, default=0.0)
    method              = Column(String(50))       # exact_match, learned, semantic, prefix_rule, nemotron
    explanation         = Column(Text)             # AI reasoning trace
    alternatives_json   = Column(JSON)             # other possible classifications
    status              = Column(String(20), default="pending")  # pending/approved/rejected/modified
    user_choice_json    = Column(JSON)             # user's override if modified
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at         = Column(DateTime(timezone=True))
    __table_args__      = (
        Index("ix_classapproval_status", "status"),
        Index("ix_classapproval_dataset", "dataset_id"),
    )
    def to_dict(self):
        return {"id":self.id,"dataset_id":self.dataset_id,"account_code":self.account_code,"account_name":self.account_name,"suggested_section":self.suggested_section,"suggested_pl_line":self.suggested_pl_line,"suggested_bs_side":self.suggested_bs_side,"confidence":self.confidence,"method":self.method,"explanation":self.explanation,"alternatives":self.alternatives_json,"status":self.status,"user_choice":self.user_choice_json,"created_at":self.created_at.isoformat() if self.created_at else None,"resolved_at":self.resolved_at.isoformat() if self.resolved_at else None}


class AuthAuditEvent(Base):
    """Authentication and authorization audit trail (Phase G-4)."""
    __tablename__ = "auth_audit_events"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    event_type      = Column(String(50), nullable=False)  # login_success|login_failure|data_access|rbac_violation|token_revoked
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email           = Column(String(255))
    ip_address      = Column(String(50))
    resource_type   = Column(String(50))    # dataset|report|agent_chat
    resource_id     = Column(Integer)
    detail          = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__  = (
        Index("ix_auth_audit_type", "event_type"),
        Index("ix_auth_audit_user", "user_id"),
        Index("ix_auth_audit_created", "created_at"),
    )
    def to_dict(self):
        return {"id":self.id,"event_type":self.event_type,"user_id":self.user_id,"email":self.email,"ip_address":self.ip_address,"resource_type":self.resource_type,"resource_id":self.resource_id,"detail":self.detail,"created_at":self.created_at.isoformat() if self.created_at else None}


class RevokedToken(Base):
    """Server-side token blacklist for logout/revocation (Phase G-4)."""
    __tablename__ = "revoked_tokens"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    jti             = Column(String(100), unique=True, nullable=False, index=True)
    user_id         = Column(Integer, nullable=False)
    revoked_at      = Column(DateTime(timezone=True), server_default=func.now())
    expires_at      = Column(DateTime(timezone=True))
    def to_dict(self):
        return {"id":self.id,"jti":self.jti,"user_id":self.user_id,"revoked_at":self.revoked_at.isoformat() if self.revoked_at else None,"expires_at":self.expires_at.isoformat() if self.expires_at else None}


# ═══════════════════════════════════════════════════════════════════
# Phase I: Decision Intelligence + Prediction Learning + Monitoring
# ═══════════════════════════════════════════════════════════════════

class DecisionAction(Base):
    """Ranked business action generated by the Decision Intelligence Engine (Phase I)."""
    __tablename__ = "decision_actions"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    action_type      = Column(String(50), nullable=False)  # cost_reduction|revenue_growth|risk_mitigation|capital_optimization|operational_efficiency
    company          = Column(String(100), default=_default_company, index=True)
    description      = Column(Text, nullable=False)
    expected_impact  = Column(DecimalString(precision=2), default="0")
    implementation_cost = Column(DecimalString(precision=2), default="0")
    roi_estimate     = Column(DecimalString(precision=2), default="0")
    risk_level       = Column(String(20), default="medium")  # low|medium|high|critical
    time_horizon     = Column(String(30), default="short_term")  # immediate|short_term|medium_term|long_term
    status           = Column(String(20), default="proposed")  # proposed|accepted|rejected|implemented
    composite_score  = Column(DecimalString(precision=4), default="0")
    source_signal    = Column(String(100))
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_decision_type", "action_type"),
        Index("ix_decision_status", "status"),
        Index("ix_decision_dataset", "dataset_id"),
    )
    def to_dict(self):
        return {"id":self.id,"action_type":self.action_type,"description":self.description,"expected_impact":float(self.expected_impact) if self.expected_impact else 0,"implementation_cost":float(self.implementation_cost) if self.implementation_cost else 0,"roi_estimate":float(self.roi_estimate) if self.roi_estimate else 0,"risk_level":self.risk_level,"time_horizon":self.time_horizon,"status":self.status,"composite_score":float(self.composite_score) if self.composite_score else 0,"source_signal":self.source_signal,"dataset_id":self.dataset_id,"created_at":self.created_at.isoformat() if self.created_at else None}


class PredictionRecord(Base):
    """Stored prediction for tracking accuracy over time (Phase I)."""
    __tablename__ = "prediction_records"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    prediction_type  = Column(String(50), nullable=False)  # forecast|scenario|anomaly_flag|threshold_breach
    company          = Column(String(100), default=_default_company, index=True)
    metric           = Column(String(100), nullable=False)
    predicted_value  = Column(DecimalString(precision=2), nullable=False)
    confidence       = Column(DecimalString(precision=4), default="0.5")
    source_method    = Column(String(50))  # moving_avg|exp_smoothing|linear_regression|ensemble|scenario_engine
    prediction_period = Column(String(50))
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    resolved         = Column(Boolean, default=False)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_pred_type", "prediction_type"),
        Index("ix_pred_metric", "metric"),
        Index("ix_pred_resolved", "resolved"),
    )
    def to_dict(self):
        return {"id":self.id,"prediction_type":self.prediction_type,"metric":self.metric,"predicted_value":float(self.predicted_value) if self.predicted_value else 0,"confidence":float(self.confidence) if self.confidence else 0,"source_method":self.source_method,"prediction_period":self.prediction_period,"dataset_id":self.dataset_id,"resolved":self.resolved,"created_at":self.created_at.isoformat() if self.created_at else None}


class PredictionOutcome(Base):
    """Actual outcome matched against a prediction (Phase I)."""
    __tablename__ = "prediction_outcomes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id    = Column(Integer, ForeignKey("prediction_records.id", ondelete="CASCADE"), nullable=False)
    actual_value     = Column(DecimalString(precision=2), nullable=False)
    error_pct        = Column(DecimalString(precision=2), default="0")
    direction_correct = Column(Boolean, default=True)
    magnitude_accuracy = Column(DecimalString(precision=4), default="0")  # 0-1 scale
    resolved_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_outcome_pred", "prediction_id"),
    )
    def to_dict(self):
        return {"id":self.id,"prediction_id":self.prediction_id,"actual_value":float(self.actual_value) if self.actual_value else 0,"error_pct":float(self.error_pct) if self.error_pct else 0,"direction_correct":self.direction_correct,"magnitude_accuracy":float(self.magnitude_accuracy) if self.magnitude_accuracy else 0,"resolved_at":self.resolved_at.isoformat() if self.resolved_at else None}


class Alert(Base):
    """Monitoring alert triggered by rule evaluation (Phase I)."""
    __tablename__ = "alerts"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    alert_type       = Column(String(50), nullable=False)  # threshold_breach|anomaly_spike|forecast_deviation|bs_violation
    company          = Column(String(100), default=_default_company, index=True)
    severity         = Column(String(20), nullable=False)  # info|warning|critical|emergency
    metric           = Column(String(100))
    threshold_value  = Column(DecimalString(precision=2))
    current_value    = Column(DecimalString(precision=2))
    message          = Column(Text, nullable=False)
    is_active        = Column(Boolean, default=True)
    acknowledged_at  = Column(DateTime(timezone=True), nullable=True)
    rule_id          = Column(Integer, nullable=True)
    dataset_id       = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_alert_type", "alert_type"),
        Index("ix_alert_severity", "severity"),
        Index("ix_alert_active", "is_active"),
        Index("ix_alert_created", "created_at"),
    )
    def to_dict(self):
        return {"id":self.id,"alert_type":self.alert_type,"severity":self.severity,"metric":self.metric,"threshold_value":float(self.threshold_value) if self.threshold_value else None,"current_value":float(self.current_value) if self.current_value else None,"message":self.message,"is_active":self.is_active,"acknowledged_at":self.acknowledged_at.isoformat() if self.acknowledged_at else None,"rule_id":self.rule_id,"dataset_id":self.dataset_id,"created_at":self.created_at.isoformat() if self.created_at else None}


class MonitoringRule(Base):
    """Configurable monitoring rule for automated alerting (Phase I)."""
    __tablename__ = "monitoring_rules"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    rule_type        = Column(String(50), nullable=False)  # threshold|anomaly|forecast_deviation|bs_equation
    company          = Column(String(100), default=_default_company, index=True)
    metric           = Column(String(100), nullable=False)
    operator         = Column(String(10), nullable=False)  # gt|lt|gte|lte|eq|neq|deviation_pct
    threshold        = Column(DecimalString(precision=2), nullable=False)
    severity         = Column(String(20), default="warning")
    cooldown_minutes = Column(Integer, default=60)
    is_enabled       = Column(Boolean, default=True)
    description      = Column(Text)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_rule_type", "rule_type"),
        Index("ix_rule_enabled", "is_enabled"),
    )
    def to_dict(self):
        return {"id":self.id,"rule_type":self.rule_type,"metric":self.metric,"operator":self.operator,"threshold":float(self.threshold) if self.threshold else 0,"severity":self.severity,"cooldown_minutes":self.cooldown_minutes,"is_enabled":self.is_enabled,"description":self.description,"last_triggered_at":self.last_triggered_at.isoformat() if self.last_triggered_at else None,"created_at":self.created_at.isoformat() if self.created_at else None}


class FinancialDocument(Base):
    """Document store for RAG/vector search."""
    __tablename__ = "financial_documents"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    content        = Column(Text, nullable=False)
    metadata_json  = Column(JSON)                                   # {source, entity_id, period}
    document_type  = Column(String(50), nullable=False)             # transaction|revenue|budget|report|rule|memory
    embedding_id   = Column(String(200))                            # chromadb doc ID
    company        = Column(String(100), default=_default_company, index=True)
    dataset_id     = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    is_indexed     = Column(Boolean, default=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_findoc_type","document_type"), Index("ix_findoc_indexed","is_indexed"),)
    def to_dict(self):
        return {"id":self.id,"document_type":self.document_type,"content":self.content[:200] if self.content else "","metadata_json":self.metadata_json,"is_indexed":self.is_indexed,"created_at":self.created_at.isoformat() if self.created_at else None}


class KnowledgeEntityRecord(Base):
    """Persisted knowledge graph entity (Phase 8 — v2 KG persistence)."""
    __tablename__ = "knowledge_entities"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    entity_id      = Column(String(200), nullable=False, unique=True, index=True)
    entity_type    = Column(String(50), nullable=False, index=True)
    label_en       = Column(String(500), nullable=False)
    label_ka       = Column(String(500), default="")
    description    = Column(Text, default="")
    properties     = Column(JSON, default={})
    is_dynamic     = Column(Boolean, default=False)  # True = pattern/correction (survives rebuilds)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("ix_kg_entity_type", "entity_type"),
        Index("ix_kg_entity_dynamic", "is_dynamic"),
    )
    def to_dict(self):
        return {"id": self.id, "entity_id": self.entity_id, "entity_type": self.entity_type,
                "label_en": self.label_en, "label_ka": self.label_ka, "description": self.description,
                "properties": self.properties, "is_dynamic": self.is_dynamic,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class KnowledgeRelationRecord(Base):
    """Persisted knowledge graph relationship (Phase 8)."""
    __tablename__ = "knowledge_relations"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    source_entity_id = Column(String(200), nullable=False, index=True)
    target_entity_id = Column(String(200), nullable=False, index=True)
    relation_type    = Column(String(50), nullable=False)
    label            = Column(String(255), default="")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__   = (
        Index("ix_kg_rel_source", "source_entity_id"),
        Index("ix_kg_rel_target", "target_entity_id"),
        Index("ix_kg_rel_type", "relation_type"),
    )
    def to_dict(self):
        return {"id": self.id, "source_entity_id": self.source_entity_id,
                "target_entity_id": self.target_entity_id, "relation_type": self.relation_type,
                "label": self.label}


# =============================================================================
# SYSTEM OF RECORD MODELS (Phase 15-17)
# =============================================================================

class JournalEntryRecord(Base):
    """Persistent double-entry journal entry — the atomic unit of accounting."""
    __tablename__ = "journal_entries"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    document_number  = Column(String(50), nullable=False, unique=True, index=True)
    posting_date     = Column(DateTime(timezone=True), nullable=False)
    period           = Column(String(50), nullable=False, index=True)  # "January 2026"
    fiscal_year      = Column(Integer, nullable=False)
    description      = Column(Text, nullable=False)
    company          = Column(String(100), default=_default_company, index=True)
    status           = Column(String(20), nullable=False, default="draft")  # draft|posted|reversed
    reference        = Column(String(200))  # External reference (invoice #, etc.)
    currency         = Column(String(10), default="GEL")
    source_type      = Column(String(50))  # manual|upload|closing|adjustment|reversal
    source_id        = Column(Integer)  # Link to source (dataset_id, etc.)
    total_debit      = Column(String(50), default="0")  # DecimalString
    total_credit     = Column(String(50), default="0")  # DecimalString
    document_hash    = Column(String(64))  # SHA256 for immutability verification
    is_immutable     = Column(Boolean, default=False)  # True after posting
    created_by       = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_by        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    posted_at        = Column(DateTime(timezone=True), nullable=True)
    reversed_at      = Column(DateTime(timezone=True), nullable=True)
    reversal_of_id   = Column(Integer, ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    __table_args__   = (
        Index("ix_je_document", "document_number"),
        Index("ix_je_period", "period"),
        Index("ix_je_status", "status"),
        Index("ix_je_posting_date", "posting_date"),
        Index("ix_je_fiscal_year", "fiscal_year"),
    )
    def to_dict(self):
        return {
            "id": self.id, "document_number": self.document_number,
            "posting_date": self.posting_date.isoformat() if self.posting_date else None,
            "period": self.period, "fiscal_year": self.fiscal_year,
            "description": self.description, "status": self.status,
            "reference": self.reference, "currency": self.currency,
            "source_type": self.source_type, "total_debit": self.total_debit,
            "total_credit": self.total_credit, "document_hash": self.document_hash,
            "is_immutable": self.is_immutable,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


class PostingLineRecord(Base):
    """Individual debit or credit line within a journal entry."""
    __tablename__ = "posting_lines"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    line_number      = Column(Integer, nullable=False)
    account_code     = Column(String(50), nullable=False, index=True)
    account_name     = Column(String(500))
    cost_center      = Column(String(50), index=True)
    profit_center    = Column(String(50))
    debit            = Column(String(50), default="0")  # DecimalString
    credit           = Column(String(50), default="0")  # DecimalString
    description      = Column(Text)
    tax_code         = Column(String(20))
    currency         = Column(String(10), default="GEL")
    __table_args__   = (
        Index("ix_pl_journal", "journal_entry_id"),
        Index("ix_pl_account", "account_code"),
        Index("ix_pl_cost_center", "cost_center"),
    )
    def to_dict(self):
        return {
            "id": self.id, "journal_entry_id": self.journal_entry_id,
            "line_number": self.line_number, "account_code": self.account_code,
            "account_name": self.account_name, "cost_center": self.cost_center,
            "debit": self.debit, "credit": self.credit,
            "description": self.description, "tax_code": self.tax_code,
        }


class DocumentNumberSequence(Base):
    """Gapless sequential document numbering per fiscal year."""
    __tablename__ = "document_number_sequences"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    prefix       = Column(String(20), nullable=False, default="JE")  # JE, AP, AR, etc.
    fiscal_year  = Column(Integer, nullable=False)
    next_number  = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        Index("ix_docseq_prefix_year", "prefix", "fiscal_year", unique=True),
    )


class FiscalPeriod(Base):
    """Accounting period with open/close control."""
    __tablename__ = "fiscal_periods"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    period_name  = Column(String(50), nullable=False, unique=True)  # "January 2026"
    fiscal_year  = Column(Integer, nullable=False)
    start_date   = Column(DateTime(timezone=True), nullable=False)
    end_date     = Column(DateTime(timezone=True), nullable=False)
    status       = Column(String(20), nullable=False, default="open")  # open|soft_close|hard_close
    closed_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at    = Column(DateTime(timezone=True), nullable=True)
    reopened_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopened_at  = Column(DateTime(timezone=True), nullable=True)
    closing_je_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    __table_args__ = (
        Index("ix_fp_period", "period_name"),
        Index("ix_fp_year", "fiscal_year"),
        Index("ix_fp_status", "status"),
    )
    def to_dict(self):
        return {
            "id": self.id, "period_name": self.period_name,
            "fiscal_year": self.fiscal_year, "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


class ChangeLog(Base):
    """Field-level immutable audit trail for all financial records."""
    __tablename__ = "change_log"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    table_name   = Column(String(100), nullable=False, index=True)
    record_id    = Column(Integer, nullable=False)
    field_name   = Column(String(100), nullable=False)
    old_value    = Column(Text)
    new_value    = Column(Text)
    change_type  = Column(String(20), nullable=False)  # create|update|delete
    changed_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at   = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_changelog_table", "table_name"),
        Index("ix_changelog_record", "table_name", "record_id"),
        Index("ix_changelog_time", "changed_at"),
    )


class AuditTrailEntry(Base):
    """Field-level audit trail for journal entries, posting lines, and periods."""
    __tablename__ = "audit_trail"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    entity_type   = Column(String(100), nullable=False)   # "journal_entry", "posting_line", "period"
    entity_id     = Column(Integer, nullable=False)
    field_name    = Column(String(100), nullable=False)
    old_value     = Column(Text, nullable=True)
    new_value     = Column(Text, nullable=True)
    changed_by    = Column(String(100), default="system")
    changed_at    = Column(DateTime(timezone=True), server_default=func.now())
    change_reason = Column(Text, nullable=True)
    session_id    = Column(String(50), nullable=True)
    __table_args__ = (
        Index("ix_trail_entity", "entity_type", "entity_id"),
        Index("ix_trail_type", "entity_type"),
        Index("ix_trail_time", "changed_at"),
        Index("ix_trail_session", "session_id"),
    )
    def to_dict(self):
        return {
            "id": self.id, "entity_type": self.entity_type, "entity_id": self.entity_id,
            "field_name": self.field_name, "old_value": self.old_value, "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "change_reason": self.change_reason, "session_id": self.session_id,
        }


class TransformationLineage(Base):
    """Data lineage graph: tracks every transformation step between entities."""
    __tablename__ = "transformation_lineage"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    source_type     = Column(String(100), nullable=False)   # "dataset", "parsed_row", "journal_entry"
    source_id       = Column(Integer, nullable=False)
    target_type     = Column(String(100), nullable=False)   # "journal_entry", "posting_line", "statement_line"
    target_id       = Column(Integer, nullable=False)
    transformation  = Column(String(200), nullable=False)   # "ingestion", "classification", "posting", "aggregation"
    metadata_json   = Column(Text, nullable=True)            # JSON string with extra details
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_tl_source", "source_type", "source_id"),
        Index("ix_tl_target", "target_type", "target_id"),
        Index("ix_tl_transformation", "transformation"),
        Index("ix_tl_created", "created_at"),
    )
    def to_dict(self):
        return {
            "id": self.id, "source_type": self.source_type, "source_id": self.source_id,
            "target_type": self.target_type, "target_id": self.target_id,
            "transformation": self.transformation, "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MarketingRequest(Base):
    """Lead generation model for capturing marketing requests from the landing page."""
    __tablename__ = "marketing_requests"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    email       = Column(String(255), nullable=False)
    name        = Column(String(255))
    company     = Column(String(255))
    status      = Column(String(20), default="pending")  # pending|contacted|archived
    metadata_json = Column(JSON)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_marketing_email", "email"),
        Index("ix_marketing_created", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "company": self.company,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
