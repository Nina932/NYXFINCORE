"""
FinAI Evaluation Engine — Tests AI reasoning quality on financial cases.
=========================================================================

Components:
  - EvalCaseLoader: Loads evaluation_cases.json
  - GroundTruthMatcher: Semantic similarity matching (keyword + ratio-based)
  - HallucinationDetector: Checks AI output against source data
  - InsightScorer: Scores depth/accuracy of AI insights
  - JudgeAgent: LLM-as-judge for qualitative evaluation
  - EvalEngine: Orchestrates the full evaluation pipeline

Scoring (100 points max):
  - Ground truth detection: 40 pts (did it find the hidden anomalies?)
  - Insight quality:        30 pts (did it provide expected insights?)
  - No hallucination:       20 pts (did it stay grounded in data?)
  - Judge assessment:        10 pts (qualitative LLM evaluation)
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Data Types ──────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    case_id: str
    difficulty: str
    description: str
    data: Dict[str, Any]
    ground_truth: Dict[str, Any]


@dataclass
class EvalResult:
    case_id: str
    difficulty: str
    description: str
    ai_output: str
    ground_truth_score: float       # 0-1
    ground_truth_matches: List[str]
    ground_truth_misses: List[str]
    insight_score: float            # 0-1
    insight_matches: List[str]
    insight_misses: List[str]
    hallucination_detected: bool
    hallucinated_numbers: List[str]
    judge_score: float              # 0-1
    judge_feedback: str
    final_score: float              # 0-100
    grade: str                      # A+/A/B+/B/C/D/F

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "difficulty": self.difficulty,
            "description": self.description,
            "ai_output_length": len(self.ai_output),
            "ground_truth_score": round(self.ground_truth_score, 3),
            "ground_truth_matches": self.ground_truth_matches,
            "ground_truth_misses": self.ground_truth_misses,
            "insight_score": round(self.insight_score, 3),
            "insight_matches": self.insight_matches,
            "insight_misses": self.insight_misses,
            "hallucination_detected": self.hallucination_detected,
            "hallucinated_numbers": self.hallucinated_numbers,
            "judge_score": round(self.judge_score, 3),
            "judge_feedback": self.judge_feedback,
            "final_score": round(self.final_score, 1),
            "grade": self.grade,
        }


@dataclass
class EvalReport:
    cases: List[EvalResult]
    avg_score: float
    avg_ground_truth: float
    avg_insight: float
    hallucination_rate: float
    avg_judge: float
    overall_grade: str
    by_difficulty: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_cases": len(self.cases),
                "avg_score": round(self.avg_score, 1),
                "avg_ground_truth": round(self.avg_ground_truth, 3),
                "avg_insight": round(self.avg_insight, 3),
                "hallucination_rate": round(self.hallucination_rate, 3),
                "avg_judge": round(self.avg_judge, 3),
                "overall_grade": self.overall_grade,
                "by_difficulty": {k: round(v, 1) for k, v in self.by_difficulty.items()},
            },
            "cases": [c.to_dict() for c in self.cases],
        }


# ── Case Loader ─────────────────────────────────────────────────────────────

class EvalCaseLoader:
    """Loads evaluation cases from JSON file."""

    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else Path(__file__).parent.parent.parent / "data" / "evaluation_cases.json"

    def load(self) -> List[EvalCase]:
        if not self._path.exists():
            logger.warning("Evaluation cases not found: %s", self._path)
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [EvalCase(**c) for c in raw]


# ── Ground Truth Matcher ────────────────────────────────────────────────────

class GroundTruthMatcher:
    """Matches AI output against known anomalies using keyword overlap."""

    # Keyword synonyms for financial concepts
    SYNONYMS = {
        "operating cash flow": ["ocf", "cash from operations", "operating cf"],
        "net income": ["net profit", "bottom line", "earnings"],
        "non-operating": ["one-time", "non-recurring", "extraordinary", "unusual"],
        "liquidity": ["liquid", "cash position", "working capital"],
        "solvency": ["solvent", "ability to pay", "going concern"],
        "debt to equity": ["d/e", "leverage ratio", "gearing"],
        "interest coverage": ["icr", "times interest earned", "interest cover"],
        "default risk": ["bankruptcy risk", "credit risk", "insolvency"],
        "earnings quality": ["profit quality", "income quality", "sustainable earnings"],
        "cash conversion": ["cash generation", "ocf to net income", "cash ratio"],
    }

    def match(self, output: str, ground_truth: Dict[str, Any]) -> tuple[float, List[str], List[str]]:
        """Match output against hidden_anomalies.

        Returns: (score 0-1, matched items, missed items)
        """
        anomalies = ground_truth.get("hidden_anomalies", [])
        if not anomalies:
            return 1.0, [], []  # No anomalies = healthy company, full score if no false alarms

        output_lower = output.lower()
        matched = []
        missed = []

        for anomaly in anomalies:
            if self._is_detected(output_lower, anomaly):
                matched.append(anomaly)
            else:
                missed.append(anomaly)

        score = len(matched) / len(anomalies) if anomalies else 1.0
        return score, matched, missed

    def match_insights(self, output: str, ground_truth: Dict[str, Any]) -> tuple[float, List[str], List[str]]:
        """Match output against expected_insights."""
        insights = ground_truth.get("expected_insights", [])
        if not insights:
            return 1.0, [], []

        output_lower = output.lower()
        matched = []
        missed = []

        for insight in insights:
            if self._is_detected(output_lower, insight):
                matched.append(insight)
            else:
                missed.append(insight)

        score = len(matched) / len(insights) if insights else 1.0
        return score, matched, missed

    def _is_detected(self, output: str, target: str) -> bool:
        """Check if target concept is detected in output via keywords + synonyms."""
        target_lower = target.lower()

        # Direct substring match
        if target_lower in output:
            return True

        # Split into keywords and check if most appear
        keywords = [w for w in target_lower.split() if len(w) > 3]
        if keywords:
            hits = sum(1 for kw in keywords if kw in output)
            if hits / len(keywords) >= 0.6:
                return True

        # Check synonyms
        for concept, syns in self.SYNONYMS.items():
            if concept in target_lower or any(s in target_lower for s in syns):
                if concept in output or any(s in output for s in syns):
                    return True

        return False


# ── Hallucination Detector ──────────────────────────────────────────────────

class HallucinationDetector:
    """Detects fabricated numbers in AI output that don't exist in source data."""

    def detect(self, output: str, source_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Check if output contains numbers not in source data.

        Returns: (hallucination_detected, list of fabricated numbers)
        """
        output_numbers = self._extract_numbers(output)
        source_numbers = self._extract_numbers(json.dumps(source_data))

        # Also allow derived numbers (ratios, percentages, sums)
        derived = self._compute_derived_numbers(source_data)
        all_valid = source_numbers | derived

        # Numbers in output not in source or derived
        fabricated = []
        for num in output_numbers:
            if num not in all_valid and not self._is_trivial(num):
                fabricated.append(str(num))

        return len(fabricated) > 0, fabricated[:10]  # Cap at 10

    def _extract_numbers(self, text: str) -> set:
        """Extract all numbers from text."""
        # Match integers, decimals, percentages
        patterns = re.findall(r'[\d,]+\.?\d*', str(text))
        numbers = set()
        for p in patterns:
            cleaned = p.replace(',', '')
            try:
                n = float(cleaned)
                numbers.add(n)
                if n == int(n):
                    numbers.add(int(n))
            except ValueError:
                pass
        return numbers

    def _compute_derived_numbers(self, data: Dict[str, Any]) -> set:
        """Compute common financial ratios/derivations from source data."""
        derived = set()
        flat = self._flatten(data)
        values = [v for v in flat.values() if isinstance(v, (int, float)) and v != 0]

        for v in values:
            derived.add(abs(v))
            # Common rounding
            derived.add(round(v, 2))
            derived.add(round(v / 1000, 1))      # K
            derived.add(round(v / 1000000, 1))   # M

        # Pairwise ratios for financial ratios
        for i, a in enumerate(values):
            for b in values[i+1:]:
                if b != 0:
                    ratio = a / b
                    derived.add(round(ratio, 2))
                    derived.add(round(ratio * 100, 1))  # As percentage
                if a != 0:
                    ratio = b / a
                    derived.add(round(ratio, 2))
                    derived.add(round(ratio * 100, 1))

        return derived

    def _flatten(self, d: Dict, prefix: str = '') -> Dict[str, Any]:
        """Flatten nested dict."""
        items: Dict[str, Any] = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten(v, key))
            else:
                items[key] = v
        return items

    def _is_trivial(self, num: float) -> bool:
        """Check if number is trivial (0, 1, 2, common percentages)."""
        return num in {0, 1, 2, 3, 4, 5, 10, 20, 25, 30, 50, 100}


# ── Judge Agent ─────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are a Big4 audit partner evaluating a financial analysis.

Score the analysis on these criteria (each 0-10):
1. INSIGHT DEPTH: Did it find non-obvious patterns? Or just restate numbers?
2. ACCURACY: Are the claims supported by the data?
3. RISK DETECTION: Did it identify real financial risks?
4. REASONING: Is there causal logic, not just correlation?

Return ONLY a JSON object like:
{"insight_depth": 7, "accuracy": 8, "risk_detection": 6, "reasoning": 5, "feedback": "Brief 1-sentence assessment"}

Be strict. Average analyst = 5. Exceptional = 8+. Never give 10."""

class JudgeAgent:
    """LLM-as-judge for qualitative evaluation of financial analysis."""

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def judge(self, ai_output: str, case_description: str) -> tuple[float, str]:
        """Judge the AI output quality. Returns (score 0-1, feedback)."""
        if not self._llm or not await self._llm.is_available():
            return self._rule_based_judge(ai_output)

        prompt = f"Case: {case_description}\n\nAnalysis to evaluate:\n{ai_output}"

        try:
            response = await self._llm.chat(
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                complexity="capable",
                max_tokens=256,
            )
            if response:
                return self._parse_judge_response(response)
        except Exception as e:
            logger.warning("Judge LLM failed: %s", e)

        return self._rule_based_judge(ai_output)

    def _parse_judge_response(self, response: str) -> tuple[float, str]:
        """Parse the judge's JSON response."""
        try:
            # Try to extract JSON from response
            match = re.search(r'\{[^}]+\}', response)
            if match:
                data = json.loads(match.group())
                scores = [
                    data.get("insight_depth", 5),
                    data.get("accuracy", 5),
                    data.get("risk_detection", 5),
                    data.get("reasoning", 5),
                ]
                avg = sum(scores) / (len(scores) * 10)  # Normalize to 0-1
                feedback = data.get("feedback", "No feedback provided")
                return min(avg, 1.0), feedback
        except (json.JSONDecodeError, KeyError):
            pass
        return self._rule_based_judge(response)

    def _rule_based_judge(self, output: str) -> tuple[float, str]:
        """Fallback rule-based quality assessment."""
        score = 0.0
        reasons = []

        # Length check (too short = shallow)
        words = len(output.split())
        if words > 200:
            score += 0.2
            reasons.append("detailed analysis")
        elif words > 100:
            score += 0.15
        elif words > 50:
            score += 0.1
        else:
            reasons.append("too brief")

        # Financial term density
        fin_terms = ["margin", "ratio", "risk", "cash flow", "leverage",
                     "liquidity", "solvency", "profitability", "revenue",
                     "earnings", "debt", "equity", "interest", "coverage"]
        term_count = sum(1 for t in fin_terms if t in output.lower())
        term_score = min(term_count / 8, 1.0) * 0.3
        score += term_score

        # Causal reasoning markers
        causal_markers = ["because", "due to", "driven by", "caused by",
                         "resulting in", "indicates", "suggests", "implies",
                         "therefore", "consequently"]
        causal_count = sum(1 for m in causal_markers if m in output.lower())
        if causal_count >= 3:
            score += 0.3
            reasons.append("good causal reasoning")
        elif causal_count >= 1:
            score += 0.15
        else:
            reasons.append("lacks causal reasoning")

        # Risk language
        risk_terms = ["risk", "concern", "warning", "danger", "critical",
                     "unsustainable", "weak", "deteriorating"]
        risk_count = sum(1 for r in risk_terms if r in output.lower())
        if risk_count >= 2:
            score += 0.2
            reasons.append("identifies risks")
        elif risk_count >= 1:
            score += 0.1

        feedback = "; ".join(reasons) if reasons else "adequate analysis"
        return min(score, 1.0), feedback


# ── Scoring ─────────────────────────────────────────────────────────────────

def compute_final_score(
    gt_score: float,
    insight_score: float,
    hallucination: bool,
    judge_score: float,
) -> float:
    """Compute final score (0-100).

    Weights:
      - Ground truth detection: 40%
      - Insight quality:        30%
      - No hallucination:       20%
      - Judge assessment:        10%
    """
    score = 0.0
    score += gt_score * 40
    score += insight_score * 30
    score += (0.0 if hallucination else 1.0) * 20
    score += judge_score * 10
    return min(score, 100)


def score_to_grade(score: float) -> str:
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 85: return "B+"
    if score >= 80: return "B"
    if score >= 70: return "C+"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"


# ── Analysis Generator ──────────────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """You are a senior financial analyst at a Big4 firm.

Analyze the provided financial data. Focus on:
- Non-obvious anomalies and patterns
- Financial risks (liquidity, solvency, leverage, earnings quality)
- Causal reasoning (WHY something is happening, not just WHAT)
- Red flags that a junior analyst might miss

Be specific. Cite numbers. Do not summarize — provide deep analysis.
If data is missing, note what additional data would be needed."""


async def generate_analysis(data: Dict[str, Any], llm_service=None) -> str:
    """Generate AI financial analysis for an evaluation case."""
    prompt = f"Analyze this financial data:\n\n{json.dumps(data, indent=2)}"

    if llm_service and await llm_service.is_available():
        try:
            response = await llm_service.chat(
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                complexity="capable",
                max_tokens=1024,
            )
            if response:
                return response
        except Exception as e:
            logger.warning("LLM analysis failed: %s", e)

    # Fallback: rule-based analysis
    return _rule_based_analysis(data)


def _rule_based_analysis(data: Dict[str, Any]) -> str:
    """Fallback rule-based financial analysis when LLM is unavailable."""
    findings = []
    flat = {}
    for section, values in data.items():
        if isinstance(values, dict):
            for k, v in values.items():
                flat[k] = v

    # Earnings quality check
    net_income = flat.get("net_income", 0)
    ocf = flat.get("operating_cash_flow", 0)
    if net_income > 0 and ocf > 0:
        if ocf / net_income < 0.5:
            findings.append(
                f"EARNINGS QUALITY CONCERN: Operating cash flow ({ocf:,.0f}) is only "
                f"{ocf/net_income:.0%} of net income ({net_income:,.0f}). This suggests "
                f"profit may be driven by non-operating or non-cash items, indicating "
                f"low earnings quality and potentially unsustainable profit growth."
            )
        else:
            findings.append(
                f"Strong cash conversion: OCF ({ocf:,.0f}) is {ocf/net_income:.0%} "
                f"of net income ({net_income:,.0f}), indicating healthy earnings quality."
            )
    elif net_income > 0 and ocf < 0:
        findings.append(
            f"CRITICAL: Negative operating cash flow ({ocf:,.0f}) despite positive "
            f"net income ({net_income:,.0f}). This is a major red flag — the company "
            f"is profitable on paper but burning cash operationally."
        )

    # Liquidity check
    ca = flat.get("current_assets", 0)
    cl = flat.get("current_liabilities", 0)
    if ca > 0 and cl > 0:
        cr = ca / cl
        if cr < 1.0:
            findings.append(
                f"LIQUIDITY RISK: Current ratio is {cr:.2f} (current assets {ca:,.0f} "
                f"vs liabilities {cl:,.0f}). Current liabilities exceed current assets, "
                f"indicating a short-term solvency issue."
            )
        elif cr < 1.5:
            findings.append(f"Moderate liquidity: Current ratio {cr:.2f} is below ideal 1.5x threshold.")

    # Leverage check
    total_debt = flat.get("total_debt", 0)
    equity = flat.get("equity", 0)
    if total_debt > 0 and equity > 0:
        de = total_debt / equity
        if de > 3:
            findings.append(
                f"HIGH LEVERAGE: Debt-to-equity ratio is {de:.1f}x (debt {total_debt:,.0f} "
                f"vs equity {equity:,.0f}). This level of financial leverage significantly "
                f"increases default risk."
            )

    # Interest coverage
    ebit = flat.get("ebit", 0)
    interest = flat.get("interest_expense", 0)
    if ebit > 0 and interest > 0:
        icr = ebit / interest
        if icr < 1.5:
            findings.append(
                f"INTEREST COVERAGE DANGEROUSLY LOW: ICR is {icr:.2f}x (EBIT {ebit:,.0f} "
                f"vs interest {interest:,.0f}). The company barely covers its interest "
                f"payments, indicating severe default risk."
            )

    # Revenue and margin
    revenue = flat.get("revenue", 0)
    cogs = flat.get("cogs", 0)
    if revenue > 0 and cogs > 0:
        gm = (revenue - cogs) / revenue
        findings.append(f"Gross margin: {gm:.1%} (revenue {revenue:,.0f}, COGS {cogs:,.0f}).")

    rev_growth = flat.get("revenue_growth", 0)
    if rev_growth > 0.3:
        findings.append(
            f"Revenue growth of {rev_growth:.0%} is aggressive. Need to verify "
            f"whether this is sustainable or driven by one-time factors."
        )

    # Investing cash flow anomaly
    icf = flat.get("investing_cash_flow", 0)
    if icf > 0:
        findings.append(
            "UNUSUAL: Positive investing cash flow suggests asset sales or "
            "one-time investment gains, which may be inflating total cash position."
        )

    if not findings:
        findings.append(
            "The company appears to be in healthy financial condition based on "
            "available data. Key metrics are within normal ranges."
        )

    return "\n\n".join(findings)


# ── Eval Engine ─────────────────────────────────────────────────────────────

class EvalEngine:
    """Orchestrates the full evaluation pipeline."""

    def __init__(self, llm_service=None):
        self._loader = EvalCaseLoader()
        self._gt_matcher = GroundTruthMatcher()
        self._hallucination = HallucinationDetector()
        self._judge = JudgeAgent(llm_service)
        self._llm = llm_service

    async def run_all(self) -> EvalReport:
        """Run evaluation on all cases."""
        cases = self._loader.load()
        if not cases:
            return EvalReport(
                cases=[], avg_score=0, avg_ground_truth=0, avg_insight=0,
                hallucination_rate=0, avg_judge=0, overall_grade="N/A",
            )

        results = []
        for case in cases:
            result = await self.evaluate_case(case)
            results.append(result)

        return self._build_report(results)

    async def run_single(self, case_id: str) -> Optional[EvalResult]:
        """Run evaluation on a single case."""
        cases = self._loader.load()
        case = next((c for c in cases if c.case_id == case_id), None)
        if not case:
            return None
        return await self.evaluate_case(case)

    async def evaluate_case(self, case: EvalCase) -> EvalResult:
        """Evaluate a single case end-to-end."""
        # Step 1: Generate AI analysis
        ai_output = await generate_analysis(case.data, self._llm)

        # Step 2: Match against ground truth
        gt_score, gt_matches, gt_misses = self._gt_matcher.match(
            ai_output, case.ground_truth
        )

        # Step 3: Match expected insights
        ins_score, ins_matches, ins_misses = self._gt_matcher.match_insights(
            ai_output, case.ground_truth
        )

        # Step 4: Check for hallucinations
        hall_detected, hall_numbers = self._hallucination.detect(
            ai_output, case.data
        )

        # Step 5: Judge assessment
        judge_score, judge_feedback = await self._judge.judge(
            ai_output, case.description
        )

        # Step 6: Compute final score
        final = compute_final_score(gt_score, ins_score, hall_detected, judge_score)
        grade = score_to_grade(final)

        return EvalResult(
            case_id=case.case_id,
            difficulty=case.difficulty,
            description=case.description,
            ai_output=ai_output,
            ground_truth_score=gt_score,
            ground_truth_matches=gt_matches,
            ground_truth_misses=gt_misses,
            insight_score=ins_score,
            insight_matches=ins_matches,
            insight_misses=ins_misses,
            hallucination_detected=hall_detected,
            hallucinated_numbers=hall_numbers,
            judge_score=judge_score,
            judge_feedback=judge_feedback,
            final_score=final,
            grade=grade,
        )

    def _build_report(self, results: List[EvalResult]) -> EvalReport:
        """Aggregate results into a report."""
        n = len(results)
        if n == 0:
            return EvalReport(
                cases=[], avg_score=0, avg_ground_truth=0, avg_insight=0,
                hallucination_rate=0, avg_judge=0, overall_grade="N/A",
            )

        avg_score = sum(r.final_score for r in results) / n
        avg_gt = sum(r.ground_truth_score for r in results) / n
        avg_ins = sum(r.insight_score for r in results) / n
        hall_rate = sum(1 for r in results if r.hallucination_detected) / n
        avg_judge = sum(r.judge_score for r in results) / n

        # By difficulty
        by_diff: Dict[str, List[float]] = {}
        for r in results:
            by_diff.setdefault(r.difficulty, []).append(r.final_score)
        by_diff_avg = {k: sum(v) / len(v) for k, v in by_diff.items()}

        return EvalReport(
            cases=results,
            avg_score=avg_score,
            avg_ground_truth=avg_gt,
            avg_insight=avg_ins,
            hallucination_rate=hall_rate,
            avg_judge=avg_judge,
            overall_grade=score_to_grade(avg_score),
            by_difficulty=by_diff_avg,
        )

    def list_cases(self) -> List[Dict[str, Any]]:
        """List available evaluation cases."""
        cases = self._loader.load()
        return [
            {
                "case_id": c.case_id,
                "difficulty": c.difficulty,
                "description": c.description,
                "anomaly_count": len(c.ground_truth.get("hidden_anomalies", [])),
                "insight_count": len(c.ground_truth.get("expected_insights", [])),
            }
            for c in cases
        ]
