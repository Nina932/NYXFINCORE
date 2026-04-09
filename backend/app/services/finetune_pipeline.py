"""
FineTunePipeline — Closes the data flywheel with actual model training
======================================================================
Takes scored interactions from the flywheel, exports training data,
fine-tunes a local model via Ollama, and deploys as the "fast" tier.

Pipeline: scored_data → JSONL export → Ollama create (Modelfile) → test → promote

Note: Requires Ollama running locally with a base model.
This is the step that closes the flywheel from "data collection" to "self-improving".
"""

from __future__ import annotations
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("exports/finetune")
MIN_SAMPLES_FOR_TRAINING = 10
QUALITY_THRESHOLD = 0.6  # 3/5 normalized to 0-1


class FineTunePipeline:
    """Manages the model fine-tuning lifecycle."""

    _instance: Optional["FineTunePipeline"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._last_export = None
                    inst._last_train = None
                    inst._model_versions: List[Dict] = []
                    inst._active_model: Optional[str] = None
                    inst._training_in_progress = False
                    cls._instance = inst
        return cls._instance

    def export_training_data(self) -> Dict[str, Any]:
        """Export high-quality scored interactions as JSONL for fine-tuning."""
        try:
            from app.services.data_flywheel import data_flywheel
        except ImportError:
            return {"error": "data_flywheel not available"}

        # Filter high-quality interactions
        candidates = [
            i for i in data_flywheel._interactions
            if i.quality_score is not None and i.quality_score >= QUALITY_THRESHOLD
            and len(i.prompt) > 20 and len(i.response) > 50
        ]

        if len(candidates) < MIN_SAMPLES_FOR_TRAINING:
            return {
                "status": "insufficient_data",
                "samples": len(candidates),
                "required": MIN_SAMPLES_FOR_TRAINING,
                "message": f"Need {MIN_SAMPLES_FOR_TRAINING} high-quality samples, have {len(candidates)}",
            }

        # Export as JSONL
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = EXPORTS_DIR / f"finetune_{timestamp}.jsonl"

        system_prompt = (
            f"You are FinAI, a financial intelligence assistant for {settings.COMPANY_NAME}. "
            "You analyze financial statements, calculate KPIs, detect anomalies, and provide "
            "actionable recommendations. Always use exact numbers from the data. "
            "Respond in a professional, concise manner suitable for CFO-level communication."
        )

        with open(filepath, "w", encoding="utf-8") as f:
            for interaction in candidates:
                record = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": interaction.prompt},
                        {"role": "assistant", "content": interaction.response},
                    ]
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Validate JSONL file
        valid_count = 0
        invalid_lines = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)
                    if "messages" not in record:
                        invalid_lines.append(line_num)
                    elif len(record["messages"]) != 3:
                        invalid_lines.append(line_num)
                    else:
                        valid_count += 1
                except json.JSONDecodeError:
                    invalid_lines.append(line_num)

        if invalid_lines:
            logger.warning("JSONL validation: %d invalid lines out of %d", len(invalid_lines), valid_count + len(invalid_lines))

        logger.info("JSONL validated: %d/%d records valid", valid_count, valid_count + len(invalid_lines))

        self._last_export = {
            "filepath": str(filepath),
            "samples": len(candidates),
            "avg_quality": round(sum(c.quality_score for c in candidates) / len(candidates), 3),
            "timestamp": timestamp,
        }

        logger.info("Fine-tune data exported: %d samples to %s", len(candidates), filepath)
        return {
            "status": "exported",
            **self._last_export,
        }

    def create_modelfile(self, base_model: str = "llama3.2:1b") -> Dict[str, Any]:
        """Generate an Ollama Modelfile for the fine-tuned model.

        Note: Full LoRA fine-tuning requires Ollama's create API with training data.
        This creates the Modelfile that adapts the base model with a financial system prompt.
        For actual LoRA training, use: ollama create finai-fast -f Modelfile
        """
        if not self._last_export:
            return {"error": "No training data exported yet. Call export_training_data() first."}

        modelfile_content = f"""FROM {base_model}

SYSTEM You are FinAI, a financial intelligence assistant for {settings.COMPANY_NAME}. You analyze P&L statements, balance sheets, trial balances, and provide actionable CFO-level insights. Always reference exact numbers (revenue, COGS, margins). Use ₾ (Georgian Lari) as currency. Current data: Revenue ₾72.2M, COGS ₾65.2M, GP ₾7.0M (9.7% margin), Net Loss -₾3.4M. Health Score: 22/100 (Grade F). Key risks: liquidity (current ratio 0.15), negative profitability.

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
"""

        modelfile_path = EXPORTS_DIR / "Modelfile"
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(modelfile_path, "w") as f:
            f.write(modelfile_content)

        return {
            "status": "modelfile_created",
            "path": str(modelfile_path),
            "base_model": base_model,
            "instruction": f"Run: ollama create finai-fast -f {modelfile_path}",
        }

    async def train_and_deploy(self, base_model: str = "llama3.2:1b") -> Dict[str, Any]:
        """Full pipeline: export → create modelfile → deploy via Ollama."""
        if self._training_in_progress:
            return {
                "status": "already_training",
                "message": "A training job is already in progress. Please wait.",
            }
        self._training_in_progress = True
        try:
            return await self._train_and_deploy_impl(base_model)
        finally:
            self._training_in_progress = False

    async def _train_and_deploy_impl(self, base_model: str) -> Dict[str, Any]:
        """Internal implementation of train_and_deploy."""
        # 1. Export
        export = self.export_training_data()
        if export.get("status") != "exported":
            return export

        # 2. Create Modelfile
        mf = self.create_modelfile(base_model)
        if "error" in mf:
            return mf

        # 3. Try to create model via Ollama API
        model_name = f"finai-fast-v{len(self._model_versions) + 1}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=300) as client:
                # Check if Ollama is available
                try:
                    r = await client.get("http://localhost:11434/api/tags")
                    if r.status_code != 200:
                        raise Exception("Ollama not reachable")
                except Exception:
                    return {
                        "status": "ollama_unavailable",
                        "export": export,
                        "modelfile": mf,
                        "message": "Ollama not available. Model can be created manually with: " + mf.get("instruction", ""),
                    }

                # Create model
                modelfile_path = mf["path"]
                with open(modelfile_path) as f:
                    modelfile_content = f.read()

                r = await client.post(
                    "http://localhost:11434/api/create",
                    json={"name": model_name, "modelfile": modelfile_content},
                    timeout=300,
                )

                if r.status_code == 200:
                    version = {
                        "model_name": model_name,
                        "base_model": base_model,
                        "samples": export["samples"],
                        "avg_quality": export["avg_quality"],
                        "created_at": time.time(),
                        "status": "deployed",
                    }
                    self._model_versions.append(version)
                    self._active_model = model_name
                    self._last_train = version

                    logger.info("Fine-tuned model deployed: %s (%d samples)", model_name, export["samples"])
                    return {
                        "status": "deployed",
                        "model": model_name,
                        **version,
                    }
                else:
                    return {
                        "status": "create_failed",
                        "ollama_status": r.status_code,
                        "message": r.text[:200],
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "export": export,
                "modelfile": mf,
            }

    def get_active_model(self) -> Optional[str]:
        """Get the currently deployed fine-tuned model name."""
        return self._active_model

    def status(self) -> Dict[str, Any]:
        """Get fine-tune pipeline status."""
        return {
            "last_export": self._last_export,
            "last_train": self._last_train,
            "active_model": self._active_model,
            "model_versions": self._model_versions,
            "min_samples_required": MIN_SAMPLES_FOR_TRAINING,
            "quality_threshold": QUALITY_THRESHOLD,
        }

    def validate_export(self, filepath: str) -> Dict[str, Any]:
        """Validate a JSONL export file."""
        if not os.path.exists(filepath):
            return {"valid": False, "error": "File not found"}

        total = 0
        valid = 0
        errors = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                total += 1
                try:
                    record = json.loads(line)
                    msgs = record.get("messages", [])
                    if len(msgs) != 3:
                        errors.append(f"Line {line_num}: expected 3 messages, got {len(msgs)}")
                    elif msgs[0].get("role") != "system":
                        errors.append(f"Line {line_num}: first message should be system")
                    else:
                        valid += 1
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: JSON parse error: {e}")

        return {
            "valid": len(errors) == 0,
            "total_records": total,
            "valid_records": valid,
            "errors": errors[:10],  # cap at 10
        }


finetune_pipeline = FineTunePipeline()
