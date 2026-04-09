"""
vector_store.py — Advanced RAG (Retrieval-Augmented Generation) service for FinAI.

Provides semantic search over financial data to augment AI agent responses
with relevant context. Supports three backends:

1. LlamaIndex + ChromaDB (preferred) — advanced RAG with knowledge graphs
2. ChromaDB only — persistent vector embeddings with semantic similarity
3. Text search fallback — SQL LIKE-based keyword matching via FinancialDocument table

The service indexes all financial records (transactions, revenue, COGS, G&A,
budget), domain-specific rules, agent memories, and the full financial
knowledge graph (COA accounts, classification rules, financial flows,
domain concepts) into a searchable store.

The agent calls `get_context_for_query` before answering user questions to
ground its responses in actual data.
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text

from app.models.all_models import (
    Transaction, RevenueItem, COGSItem, GAExpenseItem,
    BudgetLine, FinancialDocument, AgentMemory, Dataset,
)
from app.config import settings

logger = logging.getLogger(__name__)

# Modular LlamaIndex imports
try:
    from llama_index.core import VectorStoreIndex, StorageContext, Document, QueryBundle
    from llama_index.vector_stores.postgres import PostgresVectorStore
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    logger.warning("LlamaIndex modular packages not found. Falling back to SQL search.")


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCIAL DOMAIN RULES
# ═══════════════════════════════════════════════════════════════════════════════
# Legacy 9 hardcoded rules kept for backward compatibility.
# The knowledge graph now provides 150+ indexed entities as the primary
# knowledge source. These are only used if the graph fails to load.

FINANCIAL_RULES: List[Dict[str, str]] = [
    {
        "content": (
            f"{settings.COMPANY_NAME} — fuel distribution: "
            "Wholesale (Petrol, Diesel, Bitumen) and Retail (Petrol, Diesel, CNG, LPG)"
        ),
        "doc_type": "rule",
        "rule_id": "company_overview",
    },
    {
        "content": (
            "Negative wholesale margins are a strategic market-share play — NOT an error. "
            f"{settings.COMPANY_NAME} subsidizes wholesale to maintain market dominance."
        ),
        "doc_type": "rule",
        "rule_id": "negative_margin",
    },
    {
        "content": (
            "G&A account codes: 7110=Salaries, 7150=Depreciation, 7210=Rent, "
            "7430=Transport, 7450=Communications, 7480=Bank fees, 7510=Utilities, 8130=VAT"
        ),
        "doc_type": "rule",
        "rule_id": "ga_accounts",
    },
    {
        "content": (
            "COGS = col6 (purchase cost) + col7310 (logistics/transport) "
            "+ col8230 (customs/duties)"
        ),
        "doc_type": "rule",
        "rule_id": "cogs_formula",
    },
    {
        "content": "Revenue recognition: Gross (total invoice) - VAT (18%) = Net revenue",
        "doc_type": "rule",
        "rule_id": "revenue_recognition",
    },
    {
        "content": (
            "Georgian Lari (GEL) is base currency. Financial year = calendar year."
        ),
        "doc_type": "rule",
        "rule_id": "currency_fy",
    },
    {
        "content": (
            "Fuel seasonal patterns: Diesel peaks winter (heating), "
            "Petrol peaks summer (driving), Bitumen peaks summer (road construction)"
        ),
        "doc_type": "rule",
        "rule_id": "seasonality",
    },
    {
        "content": (
            "DuPont analysis: ROE = Net Margin x Asset Turnover x Equity Multiplier"
        ),
        "doc_type": "rule",
        "rule_id": "dupont",
    },
    {
        "content": (
            "Margin waterfall: Revenue -> COGS -> Gross Margin -> G&A -> EBITDA "
            "-> D&A -> EBIT -> Finance -> EBT -> Tax -> Net Profit"
        ),
        "doc_type": "rule",
        "rule_id": "margin_waterfall",
    },
]


def _get_knowledge_graph_rules() -> List[Dict[str, str]]:
    """
    Load all knowledge graph entities as indexable rules.
    Falls back to the legacy 9 hardcoded rules if the graph fails.

    Returns list of {"content", "doc_type", "rule_id"} dicts.
    """
    try:
        from app.services.knowledge_graph import knowledge_graph
        if not knowledge_graph.is_built:
            knowledge_graph.build()
        documents = knowledge_graph.get_all_documents()
        if documents:
            logger.info(
                "Loaded %d knowledge graph documents (replacing %d legacy rules)",
                len(documents), len(FINANCIAL_RULES),
            )
            return documents
    except Exception as exc:
        logger.warning(
            "Knowledge graph unavailable (%s) — using %d legacy rules",
            exc, len(FINANCIAL_RULES),
        )
    return FINANCIAL_RULES


class VectorStoreService:
    """
    Advanced RAG knowledge store for the FinAI agent.

    Indexes financial records, domain rules, and agent memories so that
    the agent can retrieve relevant context before answering questions.
    Uses LlamaIndex + PostgresVectorStore (pgvector) on Neon for
    institutional-grade semantic search without the 500MB Vercel limit.
    """

    # ── construction ──────────────────────────────────────────────────────

    def __init__(self) -> None:
        self.table_name: str = "vector_store"
        self.schema_name: str = "public"
        self.is_initialized: bool = False
        
        self._llamaindex = HAS_LLAMA
        self._index = None
        self._vector_store = None
        
        # Prepare connection strings
        # LlamaIndex PostgresVectorStore needs:
        # 1. postgresql://... for psycopg2 (sync/DDL)
        # 2. postgresql+asyncpg://... for asyncpg (async queries)
        raw_url = settings.DATABASE_URL
        if "sqlite" in raw_url:
            self._llamaindex = False
            logger.info("SQLite detected: Vector search disabled (needs PostgreSQL/pgvector)")
        else:
            # Convert async url to sync for DDL
            self.sync_url = raw_url.replace("+asyncpg", "")
            self.async_url = raw_url if "+asyncpg" in raw_url else raw_url.replace("postgresql://", "postgresql+asyncpg://")
            logger.info("VectorStore service created with Postgres (pgvector) backend")

    # ── initialisation ────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Prepare PGVectorStore and OpenAI Embeddings. Safe to call multiple times.
        """
        if self.is_initialized or not self._llamaindex:
            return

        try:
            # Use Google Gemini for "Thin" embeddings
            from llama_index.core import Settings
            Settings.embed_model = GoogleGenAIEmbedding(
                model_name="models/text-embedding-004",
                api_key=settings.GEMINI_API_KEY
            )
            
            # Setup Postgres Vector Store
            self._vector_store = PostgresVectorStore.from_params(
                host=None, # Parsed from connection string
                port=None,
                database=None,
                user=None,
                password=None,
                table_name=self.table_name,
                schema_name=self.schema_name,
                connection_string=self.sync_url,
                async_connection_string=self.async_url,
                embed_dim=1536, # OpenAI small embedding dimension
                perform_setup=True, # Will CREATE TABLE if missing
                debug=settings.DEBUG
            )
            
            storage_context = StorageContext.from_defaults(vector_store=self._vector_store)
            # Initialize an empty index (will load existing from DB)
            self._index = VectorStoreIndex.from_documents([], storage_context=storage_context)
            
            logger.info("VectorStore initialized (mode: pgvector + openai)")
            self.is_initialized = True
        except Exception as exc:
            logger.error("Failed to initialize PostgresVectorStore: %s", exc)
            self._llamaindex = False
            self.is_initialized = True

    # ══════════════════════════════════════════════════════════════════════
    #  INDEXING
    # ══════════════════════════════════════════════════════════════════════

    async def index_dataset(
        self, dataset_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Index all financial records for *dataset_id* into the knowledge store.

        Loads transactions, revenue items, COGS items, G&A expenses, and
        budget lines, converts each to a natural-language document string,
        and stores them in LlamaIndex/ChromaDB (if available) **and** the
        ``FinancialDocument`` table (for text-search fallback & persistence).

        Returns:
            ``{"indexed": <total_count>, "dataset_id": <id>}``
        """
        await self.initialize()

        # ── fetch dataset metadata ────────────────────────────────────────
        ds_result = await db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        dataset = ds_result.scalar_one_or_none()
        if dataset is None:
            logger.warning("index_dataset: dataset %d not found", dataset_id)
            return {"indexed": 0, "dataset_id": dataset_id, "error": "Dataset not found"}

        period = dataset.period or "Unknown period"
        currency = dataset.currency or "GEL"
        source_file = dataset.original_filename or dataset.name or "Unknown file"
        dataset_name = dataset.name or ""

        documents: List[Dict[str, Any]] = []
        llama_documents = []

        # ── transactions ──────────────────────────────────────────────────
        txn_result = await db.execute(
            select(Transaction).where(Transaction.dataset_id == dataset_id)
        )
        transactions = txn_result.scalars().all()
        for txn in transactions:
            content = (
                f"{txn.counterparty or 'N/A'} | "
                f"{txn.dept or 'N/A'} | "
                f"{txn.cost_class or 'N/A'} | "
                f"{txn.amount:,.2f} {currency} | "
                f"{txn.type or 'Expense'} | "
                f"{txn.date or 'N/A'}"
            )
            doc_dict = {
                "content": content,
                "doc_type": "transaction",
                "metadata": {
                    "source": "transaction",
                    "entity_id": txn.id,
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "source_file": source_file,
                    "source_sheet": "Base",       # 1C transaction journal sheet
                    "period": period,
                    "type": txn.type or "Expense",
                    "dept": txn.dept or "",
                    "counterparty": txn.counterparty or "",
                    "amount": float(txn.amount or 0),
                    "acct_dr": txn.acct_dr or "",
                    "acct_cr": txn.acct_cr or "",
                    "cost_class": txn.cost_class or "",
                },
            }
            documents.append(doc_dict)

            # Create LlamaIndex document if available
            if self._llamaindex:
                llama_doc = Document(
                    text=content,
                    metadata={
                        **doc_dict["metadata"],
                        "doc_type": doc_dict["doc_type"]
                    }
                )
                llama_documents.append(llama_doc)

        # ── revenue items ─────────────────────────────────────────────────
        rev_result = await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
        )
        revenue_items = rev_result.scalars().all()
        for rev in revenue_items:
            content = (
                f"Revenue: {rev.product or 'N/A'} | "
                f"{rev.segment or 'Other Revenue'} | "
                f"Net: {(rev.net or 0):,.2f} {currency} | "
                f"Gross: {(rev.gross or 0):,.2f} {currency}"
            )
            doc_dict = {
                "content": content,
                "doc_type": "revenue",
                "metadata": {
                    "source": "revenue",
                    "entity_id": rev.id,
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "source_file": source_file,
                    "source_sheet": "Revenue Breakdown",
                    "period": period,
                    "product": rev.product or "",
                    "segment": rev.segment or "",
                    "category": rev.category or "",
                    "net": float(rev.net or 0),
                    "gross": float(rev.gross or 0),
                },
            }
            documents.append(doc_dict)

            if self._llamaindex:
                from llama_index.core import Document
                llama_doc = Document(
                    text=content,
                    metadata={
                        **doc_dict["metadata"],
                        "doc_type": doc_dict["doc_type"]
                    }
                )
                llama_documents.append(llama_doc)

        # ── COGS items ────────────────────────────────────────────────────
        cogs_result = await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == dataset_id)
        )
        cogs_items = cogs_result.scalars().all()
        for cogs in cogs_items:
            content = (
                f"COGS: {cogs.product or 'N/A'} | "
                f"{cogs.segment or 'Other COGS'} | "
                f"Total: {(cogs.total_cogs or 0):,.2f} {currency}"
            )
            documents.append({
                "content": content,
                "doc_type": "cogs",
                "metadata": {
                    "source": "cogs",
                    "entity_id": cogs.id,
                    "dataset_id": dataset_id,
                    "period": period,
                    "product": cogs.product or "",
                    "segment": cogs.segment or "",
                    "total_cogs": float(cogs.total_cogs or 0),
                },
            })

        # ── G&A expense items ─────────────────────────────────────────────
        ga_result = await db.execute(
            select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id)
        )
        ga_items = ga_result.scalars().all()
        for ga in ga_items:
            content = (
                f"G&A: {ga.account_code or 'N/A'} "
                f"{ga.account_name or 'N/A'} | "
                f"{(ga.amount or 0):,.2f} {currency}"
            )
            documents.append({
                "content": content,
                "doc_type": "ga_expense",
                "metadata": {
                    "source": "ga_expense",
                    "entity_id": ga.id,
                    "dataset_id": dataset_id,
                    "period": period,
                    "account_code": ga.account_code or "",
                    "account_name": ga.account_name or "",
                    "amount": float(ga.amount or 0),
                },
            })

        # ── budget lines ──────────────────────────────────────────────────
        bud_result = await db.execute(
            select(BudgetLine).where(BudgetLine.dataset_id == dataset_id)
        )
        budget_lines = bud_result.scalars().all()
        for bud in budget_lines:
            content = (
                f"Budget: {bud.line_item or 'N/A'} | "
                f"Amount: {(bud.budget_amount or 0):,.2f} {currency}"
            )
            documents.append({
                "content": content,
                "doc_type": "budget",
                "metadata": {
                    "source": "budget",
                    "entity_id": bud.id,
                    "dataset_id": dataset_id,
                    "period": period,
                    "line_item": bud.line_item or "",
                    "budget_amount": float(bud.budget_amount or 0),
                },
            })

        if not documents:
            logger.info("index_dataset: dataset %d has no records to index", dataset_id)
            return {"indexed": 0, "dataset_id": dataset_id}

        # ── persist to FinancialDocument table (always) ───────────────────
        await self._save_documents_to_db(documents, dataset_id, db)

        # ── persist to LlamaIndex + PGVectorStore (if available) ───────────
        if self._llamaindex and self._index is not None and llama_documents:
            try:
                for doc in llama_documents:
                    self._index.insert(doc)
                logger.info("Indexed %d documents into PGVectorStore", len(llama_documents))
            except Exception as exc:
                logger.warning("PGVectorStore indexing failed (%s) — continuing", exc)

        total = len(documents)
        logger.info(
            "index_dataset: indexed %d documents for dataset %d (mode: %s)",
            total,
            dataset_id,
            "pgvector" if self._llamaindex else "text_search",
        )
        return {"indexed": total, "dataset_id": dataset_id}

    # ──────────────────────────────────────────────────────────────────────

    async def index_financial_rules(self) -> Dict[str, Any]:
        """
        Index domain knowledge into the vector store.

        Loads all entities from the FinancialKnowledgeGraph (COA accounts,
        classification rules, financial flows, domain concepts — 150+
        documents) and indexes them. Falls back to 9 legacy rules if the
        knowledge graph is unavailable.

        Returns:
            ``{"indexed": <count>, "source": "knowledge_graph"|"legacy"}``
        """
        await self.initialize()

        # Load rules — knowledge graph preferred, legacy fallback
        rules = _get_knowledge_graph_rules()
        source = "knowledge_graph" if len(rules) > len(FINANCIAL_RULES) else "legacy"

        # ── LlamaIndex path (preferred) ───────────────────────────────────
        if self._llamaindex and self._index is not None:
            try:
                from app.services.knowledge_graph import knowledge_graph
                llama_docs = knowledge_graph.get_all_llamaindex_documents()
                if llama_docs:
                    for doc in llama_docs:
                        self._index.insert(doc)
                    logger.info("Indexed %d knowledge graph documents into PGVectorStore", len(llama_docs))
                    return {"indexed": len(llama_docs), "source": "pgvector"}
            except Exception as exc:
                logger.warning("PGVectorStore knowledge graph indexing failed (%s) — falling back", exc)

        # ── Note: ChromaDB path removed for 'Thin-Client' architecture ──

        count = len(rules)
        logger.info(
            "index_financial_rules: indexed %d rules (source: %s)",
            count, source,
        )
        return {"indexed": count, "source": source}

    # ──────────────────────────────────────────────────────────────────────

    async def index_agent_memories(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Index ``AgentMemory`` records so past agent learnings are
        retrievable during future conversations.

        Also adds correction-type memories to the knowledge graph
        for richer context during future agent reasoning.

        Returns:
            ``{"indexed": <count>, "corrections_added": <count>}``
        """
        await self.initialize()

        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.is_active == True)  # noqa: E712
        )
        memories = mem_result.scalars().all()

        if not memories:
            logger.info("index_agent_memories: no active memories to index")
            return {"indexed": 0, "corrections_added": 0}

        documents: List[Dict[str, Any]] = []
        corrections_added = 0

        for mem in memories:
            content = f"Agent learning: {mem.content}"
            documents.append({
                "content": content,
                "doc_type": "memory",
                "metadata": {
                    "source": "agent_memory",
                    "entity_id": mem.id,
                    "memory_type": mem.memory_type or "conversation",
                    "importance": mem.importance or 5,
                },
            })

            # Add corrections to knowledge graph for richer context
            if mem.memory_type == "correction":
                try:
                    from app.services.knowledge_graph import knowledge_graph
                    if knowledge_graph.is_built:
                        knowledge_graph.add_user_correction(
                            correction_id=mem.id,
                            content=mem.content,
                            importance=mem.importance or 7,
                        )
                        corrections_added += 1
                except Exception:
                    pass

        # ── LlamaIndex path (preferred) ───────────────────────────────────
        if self._llamaindex and self._index is not None:
            try:
                # Add memories to PGVectorStore
                for doc in documents:
                    # Create LlamaIndex Document for each memory
                    from llama_index.core import Document as LlamaDoc
                    l_doc = LlamaDoc(
                        text=doc["content"],
                        metadata=doc["metadata"]
                    )
                    self._index.insert(l_doc)
                logger.info("Indexed %d memories into PGVectorStore", len(documents))
            except Exception as exc:
                logger.warning("PGVectorStore memory indexing failed (%s) — continuing", exc)

        # ── FinancialDocument table (text search fallback) ────────────────
        await self._save_documents_to_db(documents, dataset_id=None, db=db)

        count = len(documents)
        logger.info(
            "index_agent_memories: indexed %d memories (%d corrections added to knowledge graph)",
            count, corrections_added,
        )
        return {"indexed": count, "corrections_added": corrections_added}

    # ──────────────────────────────────────────────────────────────────────

    async def index_knowledge_graph(self) -> Dict[str, Any]:
        """
        Build the knowledge graph and index all its entities
        as financial rules. This replaces the 9 legacy rules with
        150+ comprehensive domain knowledge documents.

        Call this during app startup for maximum RAG coverage.

        Returns:
            ``{"graph_entities": <count>, "indexed": <count>}``
        """
        try:
            from app.services.knowledge_graph import knowledge_graph
            entity_count = knowledge_graph.build()

            # Index all knowledge graph documents as financial rules
            result = await self.index_financial_rules()

            logger.info(
                "index_knowledge_graph: graph=%d entities, indexed=%d documents",
                entity_count, result.get("indexed", 0),
            )
            return {
                "graph_entities": entity_count,
                "indexed": result.get("indexed", 0),
                "source": result.get("source", "unknown"),
            }
        except Exception as exc:
            logger.error("index_knowledge_graph failed: %s", exc)
            return {"graph_entities": 0, "indexed": 0, "error": str(exc)}

    # ══════════════════════════════════════════════════════════════════════
    #  SEARCH
    # ══════════════════════════════════════════════════════════════════════

    async def search(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge store for documents relevant to *query*.

        Returns:
            List of {"content", "score", "metadata", "source"} dicts.
        """
        await self.initialize()

        if not query or not query.strip():
            return []

        # ── PGVectorStore path ─────────────────────────────────────────────
        if self._llamaindex and self._index is not None:
            try:
                query_bundle = QueryBundle(query_str=query)
                retriever = self._index.as_retriever(similarity_top_k=n_results)
                # Use async retrieve for better performance in FastAPI
                nodes = await retriever.aretrieve(query_bundle)

                formatted_results = []
                for node in nodes:
                    formatted_results.append({
                        "content": node.node.text,
                        "score": node.score,
                        "metadata": node.node.metadata,
                        "source": "pgvector"
                    })
                return formatted_results
            except Exception as exc:
                logger.warning("PGVectorStore search failed (%s) — falling back to text search", exc)

        # ── Text-search fallback ──────────────────────────────────────────
        return await self._search_text_fallback(query, n_results)

    # ──────────────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        db: AsyncSession,
        k: int = 5,
        use_nemo_retriever: bool = False,
    ) -> str:
        """Unified retrieval with optional NeMo Retriever boost.

        When use_nemo_retriever=True and NVIDIA_API_KEY is configured,
        this will use NeMo Retriever embedding for better multilingual
        and financial document retrieval. Currently logs and falls back
        to ChromaDB — implement NIM call when you enable it.
        """
        if use_nemo_retriever:
            try:
                from app.config import settings
                if settings.NVIDIA_API_KEY:
                    logger.info("[NeMo Retriever] Enabled for query: %s", query[:100])
                    # Future: call NeMo Retriever NIM endpoint for better-ranked chunks
                    # For now: fall through to existing retrieval
            except Exception:
                pass

        return await self.get_context_for_query(query, db, n_results=k)

    async def get_context_for_query(
        self,
        query: str,
        db: AsyncSession,
        n_results: int = 5,
    ) -> str:
        """
        Build a context string for the AI agent — convenience wrapper
        that returns only the formatted text (backward compatible).
        """
        text, _ = await self.get_context_with_sources(query, db, n_results=n_results)
        return text

    async def get_context_with_sources(
        self,
        query: str,
        db: AsyncSession,
        n_results: int = 5,
    ) -> tuple:
        """
        Build context string AND return source metadata for citation generation.

        This is the citation-aware version of ``get_context_for_query``.
        Used by InsightAgent to attach provenance to every retrieved fact.

        Returns:
            (context_text: str, sources: List[Dict]) where each source has:
            {content, score, source_type, entity_id, dataset_id, period,
             account_code, amount, product, dept, counterparty, source}
        """
        if not query or not query.strip():
            return "", []

        try:
            context_parts: List[str] = []
            all_sources: List[Dict] = []

            # ── Knowledge graph: account-specific context ──────────────
            kg_context = self._get_knowledge_graph_context(query)
            if kg_context:
                context_parts.append(kg_context)

            # ── Vector store / text search ─────────────────────────────
            if not self._llamaindex or self._index is None:
                results = await self._search_text_fallback_with_db(query, n_results, db)
            else:
                results = await self.search(query, n_results=n_results)

            if results:
                lines = []
                for r in results:
                    content = r.get("content", "").strip()
                    if content:
                        lines.append(f"- {content}")
                    # Preserve full metadata for citation system
                    meta = r.get("metadata", {}) or {}
                    all_sources.append({
                        "content":      content,
                        "score":        r.get("score", 0.0),
                        "source_type":  meta.get("source") or meta.get("doc_type", "unknown"),
                        "entity_id":    meta.get("entity_id"),
                        "dataset_id":   meta.get("dataset_id"),
                        "period":       meta.get("period"),
                        "account_code": meta.get("account_code"),
                        "amount":       meta.get("amount"),
                        "product":      meta.get("product"),
                        "dept":         meta.get("dept"),
                        "counterparty": meta.get("counterparty"),
                        "segment":      meta.get("segment"),
                        "raw_meta":     meta,
                    })
                if lines:
                    context_parts.append("Relevant data:\n" + "\n".join(lines))

            # ── Uploaded document chunks (PDF, Word, Excel, text) ───────
            # Search the "finai_documents" collection for relevant uploaded files
            try:
                doc_results = await self.search_documents(query, n_results=3, db=db)
                if doc_results:
                    doc_lines = []
                    for r in doc_results:
                        content = r.get("content", "").strip()
                        meta = r.get("metadata", {}) or {}
                        if content and r.get("score", 0) > 0.3:  # relevance threshold
                            doc_lines.append(
                                f"- [{meta.get('filename', 'document')} "
                                f"chunk {meta.get('chunk_index', '?')}] {content}"
                            )
                            all_sources.append({
                                "content":       content,
                                "score":         r.get("score", 0.0),
                                "source_type":   "document",
                                "source":        "document",
                                "entity_id":     meta.get("document_id"),
                                "source_file":   meta.get("filename", ""),
                                "document_type": meta.get("document_type", ""),
                                "period":        meta.get("period", ""),
                                "chunk_index":   meta.get("chunk_index"),
                                "raw_meta":      meta,
                            })
                    if doc_lines:
                        context_parts.append(
                            "From uploaded documents:\n" + "\n".join(doc_lines)
                        )
            except Exception as doc_exc:
                logger.debug("Document search failed in get_context_with_sources: %s", doc_exc)

            # ── OAG: Ontology-Augmented Generation (Palantir pattern) ──
            # Retrieve typed ontology objects instead of raw text chunks.
            # This gives the LLM structured, validated data to reason over.
            try:
                from app.services.ontology_query import ontology_query_engine
                oag_result = await ontology_query_engine.natural_query(query)
                if oag_result.objects:
                    oag_lines = []
                    for obj in oag_result.objects[:8]:
                        props = obj.properties
                        name = props.get("name_en") or props.get("code") or props.get("metric") or obj.object_id
                        # Build typed context line
                        key_props = {k: v for k, v in props.items()
                                     if v is not None and k not in ("name_en", "name_ka", "description")
                                     and not isinstance(v, (dict, list))}
                        prop_str = ", ".join(f"{k}={v}" for k, v in list(key_props.items())[:6])
                        oag_lines.append(f"- [{obj.object_type}] {name}: {prop_str}")
                        all_sources.append({
                            "content": f"[{obj.object_type}] {name}",
                            "score": 1.0,
                            "source_type": "ontology",
                            "entity_id": obj.object_id,
                            "raw_meta": {"object_type": obj.object_type, "properties": key_props},
                        })
                    if oag_lines:
                        context_parts.insert(0, f"Ontology objects ({oag_result.count} found):\n" + "\n".join(oag_lines))
            except Exception as oag_exc:
                logger.debug("OAG context failed: %s", oag_exc)

            if not context_parts:
                return "", all_sources

            return "Relevant context:\n" + "\n\n".join(context_parts), all_sources

        except Exception as exc:
            logger.error("get_context_with_sources failed: %s", exc)
            return "", []

    def _get_knowledge_graph_context(self, query: str) -> str:
        """
        Extract relevant context from the knowledge graph.

        Two enrichment strategies that BOTH run (additive, not mutually exclusive):
        1. Account code detection (e.g., "what is 7310?") → deep hierarchy + flows
        2. General concept/keyword search → domain knowledge matches

        Account code regex filters out years (2020-2030) and common non-account
        numbers to reduce false positives.
        """
        try:
            from app.services.knowledge_graph import knowledge_graph
            if not knowledge_graph.is_built:
                return ""

            parts: List[str] = []

            # ── Strategy 1: Account code detection ────────────────────
            # Smart regex: match 2-4 digit numbers but exclude years (2020-2030),
            # common non-account numbers, and percentages
            year_pattern = {str(y) for y in range(2020, 2031)}
            codes = re.findall(r'\b(\d{2,4})\b', query)
            seen_codes: set = set()

            for code in codes[:5]:
                # Filter out years, duplicates, and numbers that aren't account codes
                if code in year_pattern or code in seen_codes:
                    continue
                seen_codes.add(code)

                ctx = knowledge_graph.get_context_for_account(code)
                if ctx.get("classification"):
                    cls = ctx["classification"]
                    line = (
                        f"Account {code}: {cls.get('label_en', 'Unknown')} "
                        f"({cls.get('statement', '?')}/{cls.get('side', '?')})"
                    )
                    if cls.get("pl_line"):
                        line += f" P&L: {cls['pl_line']}"
                    if ctx.get("hierarchy"):
                        line += f" Hierarchy: {' > '.join(ctx['hierarchy'])}"
                    parts.append(line)

                    # Related flows
                    for flow in ctx.get("related_flows", [])[:2]:
                        parts.append(
                            f"  Flow: {flow['title']}"
                            + (f" Formula: {flow['formula']}" if flow.get("formula") else "")
                        )

            # ── Strategy 2: General knowledge graph search ────────────
            # ALWAYS runs (not just when strategy 1 finds nothing)
            # so queries like "DuPont analysis for account 7310" get both
            concept_results = knowledge_graph.query(query, max_results=3)
            for entity in concept_results:
                # Skip if we already have this entity from account lookup
                if entity.entity_type == "account" and entity.entity_id in {
                    f"coa_{c}" for c in seen_codes
                }:
                    continue
                desc = entity.description[:200] if entity.description else ""
                parts.append(f"Knowledge: {entity.label_en} - {desc}")

            if not parts:
                return ""

            return "Domain knowledge:\n" + "\n".join(f"  {p}" for p in parts)

        except Exception as exc:
            logger.debug("Knowledge graph context lookup failed: %s", exc)
            return ""

    # ══════════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════════

    # ── ChromaDB helpers ──────────────────────────────────────────────────

    async def _add_to_chromadb(
        self, documents: List[Dict[str, Any]], dataset_id: int
    ) -> None:
        """Upsert a batch of document dicts into the ChromaDB collection."""
        if self._collection is None:
            return

        ids: List[str] = []
        contents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for idx, doc in enumerate(documents):
            doc_id = (
                f"{doc['doc_type']}_{dataset_id}_"
                f"{doc['metadata'].get('entity_id', idx)}"
            )
            ids.append(doc_id)
            contents.append(doc["content"])

            # ChromaDB metadata values must be str | int | float | bool
            clean_meta = self._sanitise_metadata(doc["metadata"])
            metadatas.append(clean_meta)

        # ChromaDB has a batch-size limit; split into chunks of 5000
        batch_size = 5000
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            try:
                self._collection.upsert(
                    ids=ids[start:end],
                    documents=contents[start:end],
                    metadatas=metadatas[start:end],
                )
            except Exception as exc:
                logger.error(
                    "ChromaDB upsert failed (batch %d-%d): %s", start, end, exc
                )

    async def _search_chromadb(
        self,
        query: str,
        n_results: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Execute a semantic search against ChromaDB."""
        if self._collection is None:
            return []

        try:
            query_params: Dict[str, Any] = {
                "query_texts": [query],
                "n_results": min(n_results, self._collection.count() or n_results),
            }
            if filters:
                query_params["where"] = filters

            # Guard against querying an empty collection
            if self._collection.count() == 0:
                return []

            raw = self._collection.query(**query_params)

            results: List[Dict[str, Any]] = []
            if raw and raw.get("documents"):
                docs = raw["documents"][0]
                distances = raw.get("distances", [[]])[0]
                metadatas = raw.get("metadatas", [[]])[0]

                for i, doc_text in enumerate(docs):
                    # ChromaDB returns distances; convert to a 0-1 relevance score.
                    # Cosine distance in [0, 2]; similarity = 1 - distance.
                    distance = distances[i] if i < len(distances) else 0.0
                    score = max(0.0, 1.0 - distance)

                    meta = metadatas[i] if i < len(metadatas) else {}
                    results.append({
                        "content": doc_text,
                        "score": round(score, 4),
                        "metadata": meta,
                        "source": meta.get("source", "unknown"),
                    })

            return results

        except Exception as exc:
            logger.error("ChromaDB search failed: %s", exc)
            return []

    # ── Text-search fallback helpers ──────────────────────────────────────

    async def _search_text_fallback(
        self, query: str, n_results: int
    ) -> List[Dict[str, Any]]:
        """
        Keyword search against the ``FinancialDocument`` table.

        This variant is used when called from ``search()`` without a db
        session. It imports the session factory and creates its own session.
        """
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            return await self._search_text_fallback_with_db(query, n_results, db)

    async def _search_text_fallback_with_db(
        self,
        query: str,
        n_results: int,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Keyword search against the ``FinancialDocument`` table using an
        existing database session.

        Scoring: each document gets +1 for every query keyword found in its
        content (case-insensitive).  Results are sorted descending by score.
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        try:
            # Build OR-based LIKE conditions for each keyword
            like_conditions = []
            for kw in keywords:
                like_conditions.append(
                    func.lower(FinancialDocument.content).like(f"%{kw.lower()}%")
                )

            stmt = (
                select(FinancialDocument)
                .where(or_(*like_conditions))
                .limit(n_results * 3)  # over-fetch, then re-rank
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return []

            # Score each document by keyword overlap
            scored: List[Dict[str, Any]] = []
            for row in rows:
                content_lower = (row.content or "").lower()
                hit_count = sum(1 for kw in keywords if kw.lower() in content_lower)
                score = hit_count / len(keywords) if keywords else 0.0

                meta = row.metadata_json if row.metadata_json else {}
                scored.append({
                    "content": row.content,
                    "score": round(score, 4),
                    "metadata": meta,
                    "source": row.document_type or "unknown",
                })

            # Sort by score descending, then truncate
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:n_results]

        except Exception as exc:
            logger.error("Text-search fallback failed: %s", exc)
            return []

    # ── Persistence helpers ───────────────────────────────────────────────

    async def _save_documents_to_db(
        self,
        documents: List[Dict[str, Any]],
        dataset_id: Optional[int],
        db: AsyncSession,
    ) -> None:
        """
        Persist document records into the ``FinancialDocument`` table.

        Existing documents for the same dataset are deleted first to avoid
        duplicates on re-index.
        """
        try:
            # Clear previous documents for this dataset (if applicable)
            if dataset_id is not None:
                existing = await db.execute(
                    select(FinancialDocument).where(
                        FinancialDocument.dataset_id == dataset_id
                    )
                )
                for row in existing.scalars().all():
                    await db.delete(row)
                await db.flush()

            # Insert new documents
            for idx, doc in enumerate(documents):
                entity_id = doc["metadata"].get("entity_id", idx)
                embedding_id = (
                    f"{doc['doc_type']}_{dataset_id or 'global'}_{entity_id}"
                )
                fd = FinancialDocument(
                    content=doc["content"],
                    metadata_json=doc["metadata"],
                    document_type=doc["doc_type"],
                    embedding_id=embedding_id,
                    dataset_id=dataset_id,
                    is_indexed=True,
                )
                db.add(fd)

            await db.flush()

        except Exception as exc:
            logger.error(
                "Failed to save %d documents to DB (dataset=%s): %s",
                len(documents),
                dataset_id,
                exc,
            )

    # ── Utility helpers ───────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(query: str) -> List[str]:
        """
        Split a user query into searchable keywords.

        Removes common English stop-words and very short tokens so that
        SQL LIKE queries focus on meaningful terms.
        """
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "about", "between", "through", "during", "before",
            "after", "above", "below", "and", "but", "or", "nor", "not",
            "no", "so", "if", "then", "than", "too", "very", "just",
            "that", "this", "these", "those", "it", "its", "i", "me",
            "my", "we", "our", "you", "your", "he", "she", "they",
            "what", "which", "who", "whom", "how", "when", "where", "why",
            "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "only", "own", "same", "also", "much", "many",
            "show", "tell", "give", "get", "find", "list", "display",
        }

        # Tokenise: keep alphanumeric runs and Georgian script
        tokens = re.findall(r"[\w\u10A0-\u10FF]+", query.lower())
        keywords = [t for t in tokens if t not in stop_words and len(t) >= 2]

        # De-duplicate while preserving order
        seen: set = set()
        unique: List[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        return unique

    async def unified_search(
        self,
        query: str,
        n_results: int = 10,
        collections: Optional[List[str]] = None,
        rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple ChromaDB collections and merge results with reranking.

        Searches both the main knowledge collection and the documents collection,
        deduplicates, and reranks by combining semantic similarity with keyword overlap.

        Args:
            query:       Natural-language search string.
            n_results:   Maximum number of results to return.
            collections: Collections to search (defaults to both main + documents).
            rerank:      Whether to apply keyword-boost reranking.

        Returns:
            Sorted list of ``{"content", "score", "metadata", "source", "collection"}`` dicts.
        """
        await self.initialize()

        if not query or not query.strip():
            return []

        # ── Note: Unified search is now handled by the LlamaIndex PGVectorStore retriever ──
        # This legacy method is kept for signature compatibility but redirected.
        if self._llamaindex and self._index is not None:
            return await self.search(query, n_results=n_results)

        target_collections = collections or [self.collection_name, "finai_documents"]
        all_results: List[Dict[str, Any]] = []
        seen_contents: set = set()

        if self._chromadb and self._client is not None:
            for coll_name in target_collections:
                try:
                    coll = self._client.get_or_create_collection(
                        name=coll_name,
                        metadata={"hnsw:space": "cosine"},
                    )
                    if coll.count() == 0:
                        continue

                    raw = coll.query(
                        query_texts=[query],
                        n_results=min(n_results * 2, coll.count()),
                    )

                    docs = raw.get("documents", [[]])[0]
                    dists = raw.get("distances", [[]])[0]
                    metas = raw.get("metadatas", [[]])[0]

                    for doc, dist, meta in zip(docs, dists, metas):
                        content_key = doc[:200] if doc else ""
                        if content_key in seen_contents:
                            continue
                        seen_contents.add(content_key)

                        score = max(0.0, 1.0 - dist)
                        all_results.append({
                            "content": doc,
                            "score": round(score, 4),
                            "metadata": meta or {},
                            "source": (meta or {}).get("source", "unknown"),
                            "collection": coll_name,
                        })
                except Exception as exc:
                    logger.warning("Unified search failed for collection '%s': %s", coll_name, exc)

        # Apply keyword-boost reranking
        if rerank and all_results:
            keywords = self._extract_keywords(query)
            if keywords:
                for result in all_results:
                    content_lower = (result["content"] or "").lower()
                    keyword_hits = sum(1 for kw in keywords if kw.lower() in content_lower)
                    keyword_boost = min(0.15, keyword_hits / len(keywords) * 0.15)
                    result["score"] = round(result["score"] + keyword_boost, 4)

        # Sort by combined score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:n_results]

    def get_store_stats(self) -> Dict[str, Any]:
        """Return statistics about the vector store."""
        return {
            "mode": "pgvector" if self._llamaindex else "text_search",
            "initialized": self.is_initialized,
            "backend": "Neon Postgres" if self._llamaindex else "None",
            "table": self.table_name
        }

    @staticmethod
    def _sanitise_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        No-op for Postgres store which handles JSONB natively.
        """
        return meta


    # ══════════════════════════════════════════════════════════════════════
    #  DOCUMENT CHUNK INGESTION  (used by DocumentIngestionService)
    # ══════════════════════════════════════════════════════════════════════

    async def add_document_chunks(
        self,
        chunks: List[Dict[str, Any]],
        db: AsyncSession,
        collection_name: str = "finai_documents",
    ) -> int:
        """
        Index arbitrary text chunks into the vector store.

        Used by DocumentIngestionService to add uploaded files (PDFs,
        Word docs, Excel, text) to the RAG pipeline.

        Each chunk dict must have:
          ``{"id": str, "text": str, "metadata": {source_file, document_type, ...}}``

        Returns the number of chunks successfully indexed.
        """
        await self.initialize()

        if not chunks:
            return 0

        # ── FinancialDocument table (always — text search fallback) ────────
        db_docs: List[Dict[str, Any]] = []
        for chunk in chunks:
            db_docs.append({
                "content": chunk["text"],
                "doc_type": chunk.get("metadata", {}).get("document_type", "document"),
                "metadata": chunk.get("metadata", {}),
            })

        try:
            for doc in db_docs:
                fd = FinancialDocument(
                    content=doc["content"],
                    metadata_json=doc["metadata"],
                    document_type=doc["doc_type"],
                    embedding_id=chunks[db_docs.index(doc)]["id"],
                    dataset_id=None,
                    is_indexed=True,
                )
                db.add(fd)
            await db.flush()
        except Exception as exc:
            logger.error("Failed to save document chunks to DB: %s", exc)

        # ── ChromaDB (if available) ────────────────────────────────────────
        if self._chromadb and self._client is not None:
            try:
                # Use a separate collection for uploaded documents
                doc_collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                ids = [chunk["id"] for chunk in chunks]
                texts = [chunk["text"] for chunk in chunks]
                metas = [
                    self._sanitise_metadata(chunk.get("metadata", {}))
                    for chunk in chunks
                ]

                batch_size = 100
                for start in range(0, len(ids), batch_size):
                    end = start + batch_size
                    doc_collection.upsert(
                        ids=ids[start:end],
                        documents=texts[start:end],
                        metadatas=metas[start:end],
                    )

                logger.info(
                    "add_document_chunks: indexed %d chunks into collection '%s'",
                    len(chunks), collection_name,
                )
                return len(chunks)

            except Exception as exc:
                logger.error("ChromaDB document chunk indexing failed: %s", exc)

        return len(db_docs)

    async def search_documents(
        self,
        query: str,
        n_results: int = 5,
        collection_name: str = "finai_documents",
        db: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search uploaded document chunks using ChromaDB semantic similarity.

        Returns list of ``{"content", "score", "metadata"}`` dicts.
        Falls back to keyword search in FinancialDocument table if ChromaDB unavailable.
        """
        # ── pgvector semantic search ───────────────────────────────────────
        if self._llamaindex and self._index is not None:
            try:
                retriever = self._index.as_retriever(similarity_top_k=n_results)
                results = retriever.retrieve(query)
                
                formatted = []
                for node in results:
                    # Filter by logical collection if specified
                    if collection_name and node.node.metadata.get("collection") != collection_name:
                        continue
                        
                    formatted.append({
                        "content": node.node.text,
                        "score": node.score,
                        "metadata": node.node.metadata,
                    })
                return formatted
            except Exception as exc:
                logger.warning("Document pgvector search failed: %s", exc)

        # ── DB keyword-search fallback ─────────────────────────────────────
        if db is not None:
            try:
                keywords = [w.strip() for w in query.split() if len(w.strip()) > 3][:8]
                if not keywords:
                    return []
                # Build OR of LIKE filters
                from sqlalchemy import or_
                filters = [
                    FinancialDocument.content.ilike(f"%{kw}%")
                    for kw in keywords
                ]
                stmt = (
                    select(FinancialDocument)
                    .where(or_(*filters))
                    .where(FinancialDocument.is_indexed.is_(True))
                    .limit(n_results * 2)  # fetch extra, rank locally
                )
                rows = (await db.execute(stmt)).scalars().all()
                if not rows:
                    return []
                # Simple BM25-like scoring: count keyword hits
                scored = []
                q_lower = query.lower()
                for row in rows:
                    text = (row.content or "").lower()
                    hits = sum(1 for kw in keywords if kw.lower() in text)
                    meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
                    scored.append({
                        "content": row.content or "",
                        "score": min(0.45, hits / max(len(keywords), 1) * 0.45),
                        "metadata": meta,
                    })
                scored.sort(key=lambda x: x["score"], reverse=True)
                return scored[:n_results]
            except Exception as db_exc:
                logger.warning("Document DB fallback search failed: %s", db_exc)

        return []

    async def delete_document_chunks(
        self,
        document_id: int,
        db: AsyncSession,
        collection_name: str = "finai_documents",
    ) -> int:
        """
        Remove all vector store chunks for a specific document_id.

        Returns number of chunks removed.
        """
        # Remove from PGVectorStore
        removed = 0
        if self._llamaindex and self._index is not None:
            try:
                # Standard LlamaIndex PGVectorStore deletion by metadata
                # Note: This requires the vector store implementation to supported filtered deletion
                # or we delete from the underlying table directly if needed.
                # For safety and reliability, we remove from the underlying vector table.
                await db.execute(text(
                    f"DELETE FROM {self.schema_name}.{self.table_name} "
                    "WHERE (metadata_->>'document_id')::text = :doc_id"
                ), {"doc_id": str(document_id)})
                await db.flush()
                logger.info("Deleted chunks for document %d from PGVectorStore", document_id)
            except Exception as exc:
                logger.warning("Failed to delete chunks from PGVectorStore: %s", exc)

        # Remove from FinancialDocument table
        try:
            docs = await db.execute(
                select(FinancialDocument).where(
                    FinancialDocument.metadata_json["document_id"].as_string() == str(document_id)
                )
            )
            for row in docs.scalars().all():
                await db.delete(row)
            await db.flush()
        except Exception as exc:
            logger.warning("Failed to delete document chunks from DB: %s", exc)

        return removed


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

vector_store = VectorStoreService()
