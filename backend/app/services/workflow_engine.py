"""
FinAI OS — Composable Workflow Engine (Palantir AIP Logic Pattern)
==================================================================
Enables multi-step, AI-driven workflows that chain ontology tools together.

Key concepts:
  - WorkflowStep: A single operation (tool call, LLM call, condition, transform)
  - Workflow: Ordered sequence of steps with data passing between them
  - WorkflowTrigger: Auto-execute workflows on events (upload, alert, schedule)
  - WorkflowExecution: A running instance with full audit trail

Patterns implemented:
  1. Tool Chaining: output of step N → input of step N+1
  2. Conditional Branching: if step output meets condition → skip/branch
  3. LLM Integration: use Nemotron to resolve ambiguity within a step
  4. Human-in-the-Loop: pause workflow for approval at any step
  5. Error Recovery: retry with exponential backoff, fallback logic
  6. Audit Trail: every step logged with input/output/timing/errors

Usage:
    from app.services.workflow_engine import workflow_engine

    # Define a workflow
    wf = workflow_engine.create_workflow("invoice_validation", [
        Step("extract", tool="document_extract", input_map={"file": "$trigger.file"}),
        Step("match", tool="ap_match", input_map={"invoice": "$extract.result"}),
        Step("decide", type="condition", condition="$match.confidence > 0.9",
             on_true="auto_approve", on_false="human_review"),
        Step("auto_approve", tool="propose_action", input_map={...}),
        Step("human_review", type="pause", message="Review required"),
    ])

    # Execute
    result = await workflow_engine.execute("invoice_validation", trigger_data={...})
"""

import ast
import asyncio
import json
import logging
import operator
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#   DATA MODELS
# ═══════════════════════════════════════════════════════════════════

class StepType(str, Enum):
    TOOL = "tool"           # Execute an ontology tool
    LLM = "llm"             # Call LLM for reasoning/extraction
    CONDITION = "condition"  # Branch based on result
    TRANSFORM = "transform"  # Transform data between steps
    PAUSE = "pause"          # Wait for human approval
    LOOP = "loop"            # Iterate over a collection
    PARALLEL = "parallel"    # Execute multiple steps concurrently


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"  # Waiting for human input


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    step_id: str
    name: str
    step_type: StepType = StepType.TOOL
    tool_name: Optional[str] = None           # For TOOL type
    input_map: Dict[str, str] = field(default_factory=dict)  # Maps step inputs to previous outputs
    llm_prompt: Optional[str] = None          # For LLM type
    llm_output_schema: Optional[Dict] = None  # Expected LLM output structure
    condition: Optional[str] = None           # For CONDITION type: Python expression
    on_true: Optional[str] = None             # Step to jump to if condition is true
    on_false: Optional[str] = None            # Step to jump to if condition is false
    transform_fn: Optional[str] = None        # For TRANSFORM: Python expression
    pause_message: Optional[str] = None       # For PAUSE type
    retry_count: int = 2                      # Max retries on failure
    timeout_seconds: int = 60                 # Step timeout
    description: str = ""                     # Human-readable description


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    retries: int = 0


@dataclass
class WorkflowDefinition:
    """A reusable workflow template."""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    trigger_events: List[str] = field(default_factory=list)  # e.g. ["upload_complete", "alert_triggered"]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1


@dataclass
class WorkflowExecution:
    """A running or completed workflow instance."""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    current_step: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
#   VARIABLE RESOLVER — resolve $step.field references
# ═══════════════════════════════════════════════════════════════════

class VariableResolver:
    """Resolves $step_id.field references in input maps."""

    def __init__(self, execution: WorkflowExecution):
        self._exec = execution

    def resolve(self, value: Any) -> Any:
        """Resolve a value, replacing $references with actual data."""
        if isinstance(value, str) and value.startswith("$"):
            return self._resolve_ref(value)
        elif isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve(v) for v in value]
        return value

    def _resolve_ref(self, ref: str) -> Any:
        """Resolve a $step_id.field.subfield reference."""
        parts = ref[1:].split(".")  # Remove $ prefix
        if not parts:
            return None

        # $trigger.xxx → get from trigger_data
        if parts[0] == "trigger":
            data = self._exec.trigger_data
            for p in parts[1:]:
                if isinstance(data, dict):
                    data = data.get(p)
                else:
                    return None
            return data

        # $step_id.xxx → get from step results
        step_id = parts[0]
        result = self._exec.step_results.get(step_id)
        if not result or result.status != StepStatus.COMPLETED:
            return None

        data = result.output
        for p in parts[1:]:
            if isinstance(data, dict):
                data = data.get(p)
            elif isinstance(data, list) and p.isdigit():
                idx = int(p)
                data = data[idx] if idx < len(data) else None
            else:
                return None
        return data


# ═══════════════════════════════════════════════════════════════════
#   SAFE EXPRESSION EVALUATOR (replaces eval())
# ═══════════════════════════════════════════════════════════════════

_SAFE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: operator.not_,
}

_SAFE_FUNCS = {
    "len": len, "sum": sum, "max": max, "min": min,
    "abs": abs, "round": round, "str": str, "int": int,
    "float": float, "bool": bool,
}


def _safe_eval_node(node, ctx):
    """Recursively evaluate an AST node with restricted operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return ctx[node.id]
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        if node.id in _SAFE_FUNCS:
            return _SAFE_FUNCS[node.id]
        raise NameError(f"Name '{node.id}' is not allowed")
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_safe_eval_node(v, ctx) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_safe_eval_node(v, ctx) for v in node.values)
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval_node(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")
    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left, ctx)
        right = _safe_eval_node(node.right, ctx)
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op)}")
        return op_fn(left, right)
    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _safe_eval_node(comparator, ctx)
            op_fn = _SAFE_OPS.get(type(op))
            if op_fn is None:
                raise ValueError(f"Unsupported comparison: {type(op)}")
            if not op_fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        func = _safe_eval_node(node.func, ctx)
        if func not in _SAFE_FUNCS.values():
            raise ValueError(f"Function call not allowed: {func}")
        args = [_safe_eval_node(a, ctx) for a in node.args]
        return func(*args)
    if isinstance(node, ast.Attribute):
        value = _safe_eval_node(node.value, ctx)
        if isinstance(value, dict):
            return value.get(node.attr)
        raise ValueError(f"Attribute access not allowed on {type(value)}")
    if isinstance(node, ast.Subscript):
        value = _safe_eval_node(node.value, ctx)
        if isinstance(node.slice, ast.Constant):
            return value[node.slice.value]
        idx = _safe_eval_node(node.slice, ctx)
        return value[idx]
    if isinstance(node, ast.IfExp):
        test = _safe_eval_node(node.test, ctx)
        return _safe_eval_node(node.body, ctx) if test else _safe_eval_node(node.orelse, ctx)
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


def safe_eval_expression(expression: str, ctx: dict):
    """Safely evaluate a Python expression without using eval().

    Only supports: literals, comparisons, boolean logic, arithmetic,
    and a limited set of builtin functions.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}")
    return _safe_eval_node(tree, ctx)


# ═══════════════════════════════════════════════════════════════════
#   STEP EXECUTORS
# ═══════════════════════════════════════════════════════════════════

class StepExecutors:
    """Handles execution of each step type."""

    @staticmethod
    async def execute_tool(step: WorkflowStep, resolved_inputs: Dict) -> Any:
        """Execute an ontology tool."""
        from app.services.ontology_tools import ontology_tool_executor
        return await ontology_tool_executor.execute(step.tool_name, resolved_inputs)

    @staticmethod
    async def execute_llm(step: WorkflowStep, resolved_inputs: Dict) -> Any:
        """Call LLM for reasoning/extraction."""
        from app.services.local_llm import captain_llm

        # Build prompt from template + resolved inputs
        prompt = step.llm_prompt or ""
        for key, value in resolved_inputs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value) if not isinstance(value, str) else value)

        # Add output schema instruction if specified
        if step.llm_output_schema:
            prompt += f"\n\nRespond with a JSON object matching this schema: {json.dumps(step.llm_output_schema)}"
            prompt += "\nReturn ONLY valid JSON, no markdown or explanation."

        result = await captain_llm.route_and_call(prompt, context=resolved_inputs)
        content = result.get("content", "")

        # Try to parse as JSON if output schema was specified
        if step.llm_output_schema:
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_str = content
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                parsed = json.loads(json_str)
                return {"parsed": parsed, "raw": content, "model": result.get("model")}
            except (json.JSONDecodeError, IndexError):
                return {"raw": content, "model": result.get("model"), "parse_error": True}

        return {"content": content, "model": result.get("model")}

    @staticmethod
    async def execute_condition(step: WorkflowStep, resolved_inputs: Dict, execution: WorkflowExecution) -> str:
        """Evaluate a condition and return the next step ID."""
        # Build evaluation context from all completed step outputs
        ctx = {"trigger": execution.trigger_data}
        for sid, sr in execution.step_results.items():
            if sr.status == StepStatus.COMPLETED:
                ctx[sid] = sr.output

        # Also add resolved inputs
        ctx.update(resolved_inputs)

        try:
            # Safely evaluate the condition
            condition = step.condition or "False"
            # Replace $refs in the condition string
            for key, val in ctx.items():
                if isinstance(val, dict):
                    for k2, v2 in val.items():
                        condition = condition.replace(f"${key}.{k2}", repr(v2))
                condition = condition.replace(f"${key}", repr(val))

            result = safe_eval_expression(condition, ctx)
            return step.on_true if result else step.on_false
        except Exception as e:
            logger.warning(f"Condition eval error: {e}, defaulting to on_false")
            return step.on_false

    @staticmethod
    async def execute_transform(step: WorkflowStep, resolved_inputs: Dict) -> Any:
        """Transform data between steps."""
        if not step.transform_fn:
            return resolved_inputs

        try:
            # Simple key mapping and extraction
            transform = step.transform_fn
            if transform.startswith("{") and transform.endswith("}"):
                # JSON template with $references — already resolved by input_map
                return resolved_inputs
            else:
                # Python expression
                result = safe_eval_expression(transform, {"data": resolved_inputs})
                return result
        except Exception as e:
            logger.warning(f"Transform error: {e}")
            return resolved_inputs


# ═══════════════════════════════════════════════════════════════════
#   WORKFLOW ENGINE
# ═══════════════════════════════════════════════════════════════════

class WorkflowEngine:
    """
    Composable workflow execution engine.
    Chains ontology tools, LLM calls, conditions, and human approvals.
    """

    def __init__(self):
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._triggers: Dict[str, List[str]] = {}  # event → [workflow_ids]
        self._executors = StepExecutors()
        self._register_builtin_workflows()

    def _register_builtin_workflows(self):
        """Register built-in financial workflows."""

        # ── Workflow 1: Full Financial Analysis Pipeline ──
        self.register_workflow(WorkflowDefinition(
            workflow_id="financial_analysis",
            name="Full Financial Analysis",
            description="Complete financial analysis pipeline: parse → classify → derive KPIs → detect risks → generate strategy → propose actions",
            trigger_events=["upload_complete"],
            steps=[
                WorkflowStep(
                    step_id="load_data",
                    name="Load Financial Data",
                    step_type=StepType.TOOL,
                    tool_name="search_objects",
                    input_map={"type_id": "FinancialStatement", "limit": "1"},
                    description="Load the latest financial statement from ontology",
                ),
                WorkflowStep(
                    step_id="compute_kpis",
                    name="Compute KPIs",
                    step_type=StepType.TOOL,
                    tool_name="aggregate_objects",
                    input_map={"type_id": "KPI", "property": "value"},
                    description="Aggregate all KPI values for assessment",
                ),
                WorkflowStep(
                    step_id="detect_risks",
                    name="Detect Risk Signals",
                    step_type=StepType.TOOL,
                    tool_name="search_objects",
                    input_map={"type_id": "RiskSignal", "filters": {"severity": "critical"}},
                    description="Find all critical risk signals",
                ),
                WorkflowStep(
                    step_id="check_severity",
                    name="Check Risk Severity",
                    step_type=StepType.CONDITION,
                    condition="len($detect_risks.get('objects', [])) > 0",
                    on_true="generate_urgent_strategy",
                    on_false="generate_growth_strategy",
                    description="Route based on whether critical risks exist",
                ),
                WorkflowStep(
                    step_id="generate_urgent_strategy",
                    name="Generate Urgent Response",
                    step_type=StepType.LLM,
                    llm_prompt="Based on these critical financial risks: {risks}, generate an urgent response plan with 3 specific actions.",
                    input_map={"risks": "$detect_risks.objects"},
                    llm_output_schema={"actions": [{"action": "string", "priority": "string", "estimated_impact": "number"}]},
                    description="AI generates urgent response plan for critical risks",
                ),
                WorkflowStep(
                    step_id="generate_growth_strategy",
                    name="Generate Growth Strategy",
                    step_type=StepType.LLM,
                    llm_prompt="The company has no critical risks. KPI summary: {kpis}. Generate a growth acceleration strategy with 3 opportunities.",
                    input_map={"kpis": "$compute_kpis"},
                    llm_output_schema={"opportunities": [{"opportunity": "string", "estimated_roi": "string", "timeline": "string"}]},
                    description="AI generates growth strategy when no critical risks",
                ),
                WorkflowStep(
                    step_id="propose_actions",
                    name="Propose Actions",
                    step_type=StepType.TOOL,
                    tool_name="propose_action",
                    input_map={
                        "description": "Automated financial analysis complete",
                        "category": "analysis",
                        "risk_level": "low",
                    },
                    description="Create action proposal for human review",
                ),
            ],
        ))

        # ── Workflow 2: Invoice Validation ──
        self.register_workflow(WorkflowDefinition(
            workflow_id="invoice_validation",
            name="Invoice Validation",
            description="AI-powered invoice validation: extract → match against AP → check for anomalies → approve or flag",
            steps=[
                WorkflowStep(
                    step_id="extract_invoice",
                    name="Extract Invoice Data",
                    step_type=StepType.LLM,
                    llm_prompt="Extract structured data from this invoice text: {invoice_text}. Include: vendor_name, invoice_number, date, line_items (description, quantity, unit_price, amount), subtotal, tax, total.",
                    input_map={"invoice_text": "$trigger.text"},
                    llm_output_schema={
                        "vendor_name": "string",
                        "invoice_number": "string",
                        "date": "string",
                        "line_items": [{"description": "string", "quantity": "number", "unit_price": "number", "amount": "number"}],
                        "subtotal": "number",
                        "tax": "number",
                        "total": "number",
                    },
                    description="AI extracts structured invoice data from text/PDF",
                ),
                WorkflowStep(
                    step_id="match_vendor",
                    name="Match Vendor",
                    step_type=StepType.TOOL,
                    tool_name="search_objects",
                    input_map={"type_id": "Company", "filters": {"name": "$extract_invoice.parsed.vendor_name"}},
                    description="Find matching vendor in ontology",
                ),
                WorkflowStep(
                    step_id="check_duplicate",
                    name="Check for Duplicates",
                    step_type=StepType.TOOL,
                    tool_name="query_warehouse",
                    input_map={"sql": "SELECT COUNT(*) as cnt FROM dw_transactions WHERE description LIKE '%$extract_invoice.parsed.invoice_number%'"},
                    description="Check if this invoice was already processed",
                ),
                WorkflowStep(
                    step_id="validate_amounts",
                    name="Validate Amounts",
                    step_type=StepType.LLM,
                    llm_prompt="Validate this invoice: {invoice}. Check: 1) Do line items sum to subtotal? 2) Is tax rate reasonable (15-20%)? 3) Any suspicious items? Return validation result.",
                    input_map={"invoice": "$extract_invoice.parsed"},
                    llm_output_schema={"valid": "boolean", "issues": ["string"], "confidence": "number"},
                    description="AI validates invoice arithmetic and flags anomalies",
                ),
                WorkflowStep(
                    step_id="decide",
                    name="Auto-approve or Review",
                    step_type=StepType.CONDITION,
                    condition="$validate_amounts.get('parsed', {}).get('valid', False) and $validate_amounts.get('parsed', {}).get('confidence', 0) > 0.9",
                    on_true="auto_approve",
                    on_false="flag_for_review",
                    description="Auto-approve if valid with high confidence, otherwise flag",
                ),
                WorkflowStep(
                    step_id="auto_approve",
                    name="Auto-Approve Invoice",
                    step_type=StepType.TOOL,
                    tool_name="propose_action",
                    input_map={
                        "description": "Auto-approved invoice from $extract_invoice.parsed.vendor_name",
                        "category": "ap_approval",
                        "risk_level": "low",
                    },
                    description="Create auto-approval action",
                ),
                WorkflowStep(
                    step_id="flag_for_review",
                    name="Flag for Human Review",
                    step_type=StepType.TOOL,
                    tool_name="create_risk_signal",
                    input_map={
                        "signal_type": "invoice_review_required",
                        "severity": "warning",
                        "message": "Invoice requires manual review: $validate_amounts.parsed.issues",
                    },
                    description="Create risk signal for human review",
                ),
            ],
        ))

        # ── Workflow 3: Anomaly Alert Response ──
        self.register_workflow(WorkflowDefinition(
            workflow_id="anomaly_response",
            name="Anomaly Alert Response",
            description="When an anomaly is detected, automatically investigate and propose corrective actions",
            trigger_events=["alert_triggered"],
            steps=[
                WorkflowStep(
                    step_id="get_context",
                    name="Gather Context",
                    step_type=StepType.TOOL,
                    tool_name="search_objects",
                    input_map={"type_id": "KPI", "filters": {"status": "breached"}},
                    description="Find all breached KPIs for context",
                ),
                WorkflowStep(
                    step_id="get_trends",
                    name="Analyze Trends",
                    step_type=StepType.TOOL,
                    tool_name="query_warehouse",
                    input_map={"sql": "SELECT metric, value, period FROM dw_financial_snapshots WHERE metric = '$trigger.metric' ORDER BY period DESC LIMIT 12"},
                    description="Get historical data for the anomalous metric",
                ),
                WorkflowStep(
                    step_id="ai_diagnosis",
                    name="AI Diagnosis",
                    step_type=StepType.LLM,
                    llm_prompt="A financial anomaly was detected. Alert: {alert}. Breached KPIs: {kpis}. Historical trend: {trend}. Provide: 1) Root cause analysis 2) Severity assessment 3) Recommended actions",
                    input_map={
                        "alert": "$trigger",
                        "kpis": "$get_context.objects",
                        "trend": "$get_trends.results",
                    },
                    llm_output_schema={
                        "root_cause": "string",
                        "severity": "string",
                        "recommended_actions": [{"action": "string", "urgency": "string"}],
                    },
                    description="AI analyzes the anomaly and recommends actions",
                ),
                WorkflowStep(
                    step_id="propose_response",
                    name="Propose Response",
                    step_type=StepType.TOOL,
                    tool_name="propose_action",
                    input_map={
                        "description": "Response to anomaly: $ai_diagnosis.parsed.root_cause",
                        "category": "anomaly_response",
                        "risk_level": "$ai_diagnosis.parsed.severity",
                    },
                    description="Create action proposal based on AI diagnosis",
                ),
            ],
        ))

        # ── Workflow 4: Journal Posted → Reconciliation ──
        self.register_workflow(WorkflowDefinition(
            workflow_id="journal_reconciliation",
            name="Journal Posted Reconciliation",
            description="When a journal entry is posted, verify TB balance and check for anomalies",
            trigger_events=["journal_posted"],
            steps=[
                WorkflowStep(
                    step_id="check_kpis",
                    name="Check KPIs",
                    step_type=StepType.TOOL,
                    tool_name="search_objects",
                    input_map={"type_id": "KPI", "filters": {"status": "breached"}},
                    description="Check if any KPIs are breached after this posting",
                ),
                WorkflowStep(
                    step_id="flag_if_needed",
                    name="Flag Issues",
                    step_type=StepType.CONDITION,
                    condition="len($check_kpis.get('objects', [])) > 0",
                    on_true="create_alert",
                    on_false="complete",
                    description="If KPIs breached, create alert",
                ),
                WorkflowStep(
                    step_id="create_alert",
                    name="Create Risk Signal",
                    step_type=StepType.TOOL,
                    tool_name="create_risk_signal",
                    input_map={
                        "signal_type": "post_journal_check",
                        "severity": "warning",
                        "message": "Journal posting triggered KPI breach check",
                    },
                    description="Create alert for breached KPIs after journal posting",
                ),
                WorkflowStep(
                    step_id="complete",
                    name="Complete",
                    step_type=StepType.TRANSFORM,
                    input_map={"status": "ok", "message": "Journal reconciliation complete"},
                    description="Reconciliation completed successfully",
                ),
            ],
        ))

    # ── Registration ──

    def register_workflow(self, workflow: WorkflowDefinition):
        """Register a workflow definition."""
        self._workflows[workflow.workflow_id] = workflow
        for event in workflow.trigger_events:
            self._triggers.setdefault(event, []).append(workflow.workflow_id)
        logger.info(f"Workflow registered: {workflow.workflow_id} ({len(workflow.steps)} steps)")

    def list_workflows(self) -> List[Dict]:
        """List all registered workflows."""
        return [
            {
                "workflow_id": wf.workflow_id,
                "name": wf.name,
                "description": wf.description,
                "steps": len(wf.steps),
                "triggers": wf.trigger_events,
                "version": wf.version,
            }
            for wf in self._workflows.values()
        ]

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self._workflows.get(workflow_id)

    # ── Execution ──

    async def execute(self, workflow_id: str, trigger_data: Dict[str, Any] = None) -> WorkflowExecution:
        """Execute a workflow with the given trigger data."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        execution = WorkflowExecution(
            execution_id=str(uuid.uuid4())[:12],
            workflow_id=workflow_id,
            trigger_data=trigger_data or {},
        )
        self._executions[execution.execution_id] = execution

        logger.info(f"Workflow starting: {workflow_id} (exec={execution.execution_id})")

        # Execute steps sequentially (with branching)
        step_index = 0
        step_map = {s.step_id: i for i, s in enumerate(wf.steps)}
        visited = set()

        while step_index < len(wf.steps):
            step = wf.steps[step_index]

            # Prevent infinite loops
            if step.step_id in visited:
                break
            visited.add(step.step_id)

            execution.current_step = step.step_id
            resolver = VariableResolver(execution)

            # Resolve inputs
            resolved_inputs = resolver.resolve(step.input_map) if step.input_map else {}

            # Execute with retry
            step_result = await self._execute_step(step, resolved_inputs, execution)
            execution.step_results[step.step_id] = step_result

            if step_result.status == StepStatus.FAILED:
                execution.status = WorkflowStatus.FAILED
                execution.error = step_result.error
                break
            elif step_result.status == StepStatus.PAUSED:
                execution.status = WorkflowStatus.PAUSED
                break

            # Handle branching for condition steps
            if step.step_type == StepType.CONDITION and isinstance(step_result.output, str):
                next_step_id = step_result.output
                if next_step_id and next_step_id in step_map:
                    step_index = step_map[next_step_id]
                    continue

            step_index += 1

        # Mark completed if we made it through all steps
        if execution.status == WorkflowStatus.RUNNING:
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Workflow {execution.status.value}: {workflow_id} "
                     f"({len(execution.step_results)} steps, exec={execution.execution_id})")

        # Record workflow execution in activity feed
        try:
            from app.services.activity_feed import activity_feed
            total_dur = sum(sr.duration_ms for sr in execution.step_results.values())
            trace_id = f"wf-{execution.execution_id}"
            # Record parent event
            parent_id = activity_feed.record(
                event_type="automation_triggered", resource_type="Workflow",
                resource_id=workflow_id, action="workflow_execute",
                details={
                    "execution_id": execution.execution_id,
                    "steps_completed": sum(1 for s in execution.step_results.values() if s.status == StepStatus.COMPLETED),
                    "steps_total": len(wf.steps),
                },
                status="success" if execution.status == WorkflowStatus.COMPLETED else "failure",
                duration_ms=total_dur,
                trace_id=trace_id,
            )
            # Record each step as a child span
            for sid, sr in execution.step_results.items():
                activity_feed.record(
                    event_type="function_execution", resource_type="WorkflowStep",
                    resource_id=sid, action=f"step_{sid}",
                    details={"output_type": type(sr.output).__name__ if sr.output else "none",
                             "retries": sr.retries},
                    status="success" if sr.status == StepStatus.COMPLETED else "failure",
                    duration_ms=sr.duration_ms,
                    trace_id=trace_id,
                    parent_event_id=parent_id,
                )
        except Exception:
            pass

        return execution

    async def _execute_step(self, step: WorkflowStep, resolved_inputs: Dict, execution: WorkflowExecution) -> StepResult:
        """Execute a single step with retry logic."""
        result = StepResult(
            step_id=step.step_id,
            status=StepStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        for attempt in range(step.retry_count + 1):
            try:
                t0 = time.time()

                if step.step_type == StepType.TOOL:
                    output = await self._executors.execute_tool(step, resolved_inputs)
                elif step.step_type == StepType.LLM:
                    output = await self._executors.execute_llm(step, resolved_inputs)
                elif step.step_type == StepType.CONDITION:
                    output = await self._executors.execute_condition(step, resolved_inputs, execution)
                elif step.step_type == StepType.TRANSFORM:
                    output = await self._executors.execute_transform(step, resolved_inputs)
                elif step.step_type == StepType.PAUSE:
                    result.status = StepStatus.PAUSED
                    result.output = {"message": step.pause_message or "Waiting for human approval"}
                    result.completed_at = datetime.now(timezone.utc).isoformat()
                    result.duration_ms = int((time.time() - t0) * 1000)
                    return result
                else:
                    output = resolved_inputs

                result.output = output
                result.status = StepStatus.COMPLETED
                result.completed_at = datetime.now(timezone.utc).isoformat()
                result.duration_ms = int((time.time() - t0) * 1000)
                result.retries = attempt
                return result

            except Exception as e:
                logger.warning(f"Step {step.step_id} attempt {attempt+1} failed: {e}")
                if attempt < step.retry_count:
                    await asyncio.sleep(1 * (attempt + 1))  # Linear backoff
                else:
                    result.status = StepStatus.FAILED
                    result.error = str(e)
                    result.completed_at = datetime.now(timezone.utc).isoformat()
                    result.duration_ms = int((time.time() - t0) * 1000)
                    result.retries = attempt

        return result

    # ── Event Triggers ──

    async def on_event(self, event_type: str, event_data: Dict[str, Any]) -> List[WorkflowExecution]:
        """Trigger all workflows registered for this event type."""
        workflow_ids = self._triggers.get(event_type, [])
        results = []
        for wf_id in workflow_ids:
            try:
                execution = await self.execute(wf_id, trigger_data=event_data)
                results.append(execution)
            except Exception as e:
                logger.error(f"Workflow trigger failed: {wf_id} on {event_type}: {e}")
        return results

    # ── Query ──

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        return self._executions.get(execution_id)

    def list_executions(self, workflow_id: str = None, limit: int = 20) -> List[Dict]:
        """List recent workflow executions."""
        execs = list(self._executions.values())
        if workflow_id:
            execs = [e for e in execs if e.workflow_id == workflow_id]
        execs.sort(key=lambda e: e.started_at, reverse=True)
        return [
            {
                "execution_id": e.execution_id,
                "workflow_id": e.workflow_id,
                "status": e.status.value,
                "steps_completed": sum(1 for s in e.step_results.values() if s.status == StepStatus.COMPLETED),
                "steps_total": len(self._workflows.get(e.workflow_id, WorkflowDefinition("", "", "", [])).steps),
                "started_at": e.started_at,
                "completed_at": e.completed_at,
                "duration_ms": sum(s.duration_ms for s in e.step_results.values()),
                "error": e.error,
            }
            for e in execs[:limit]
        ]

    def resume_execution(self, execution_id: str, approval: Dict[str, Any] = None) -> Optional[str]:
        """Resume a paused workflow (after human approval)."""
        execution = self._executions.get(execution_id)
        if not execution or execution.status != WorkflowStatus.PAUSED:
            return None

        # Mark the paused step as completed with approval data
        current = execution.current_step
        if current and current in execution.step_results:
            execution.step_results[current].status = StepStatus.COMPLETED
            execution.step_results[current].output = {"approved": True, "approval_data": approval or {}}

        execution.status = WorkflowStatus.RUNNING
        return execution.execution_id


# ═══════════════════════════════════════════════════════════════════
#   SINGLETON
# ═══════════════════════════════════════════════════════════════════

workflow_engine = WorkflowEngine()
