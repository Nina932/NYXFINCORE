"""
ERP Adapter Registry — Auto-detection and adapter lookup.

Usage:
    from app.adapters.registry import detect_erp_system, get_adapter

    # Auto-detect which ERP produced a file
    adapter = detect_erp_system(Path("upload.xlsx"))
    if adapter:
        accounts = adapter.parse_chart_of_accounts(Path("upload.xlsx"))

    # Get a specific adapter by name
    adapter = get_adapter("1c")
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

from app.adapters.base_adapter import BaseERPAdapter

logger = logging.getLogger(__name__)

# Global registry of adapter classes
_ADAPTERS: Dict[str, Type[BaseERPAdapter]] = {}


def register_adapter(cls: Type[BaseERPAdapter]) -> Type[BaseERPAdapter]:
    """Decorator to register an ERP adapter class.

    Usage:
        @register_adapter
        class OneCAdapter(BaseERPAdapter):
            ...
    """
    instance = cls()
    _ADAPTERS[instance.system_name] = cls
    logger.info("Registered ERP adapter: %s (%s)", instance.system_name, instance.display_name)
    return cls


def get_adapter(system_name: str) -> Optional[BaseERPAdapter]:
    """Get an adapter instance by system name."""
    cls = _ADAPTERS.get(system_name)
    if cls:
        return cls()
    return None


def list_adapters() -> List[Dict[str, str]]:
    """List all registered adapters."""
    result = []
    for name, cls in _ADAPTERS.items():
        instance = cls()
        result.append({
            "system_name": instance.system_name,
            "display_name": instance.display_name,
            "formats": instance.supported_formats,
        })
    return result


def detect_erp_system(file_path: Path) -> Optional[BaseERPAdapter]:
    """Auto-detect which ERP system produced a file.

    Runs detect() on all registered adapters and returns the one
    with the highest confidence above 0.5.

    Args:
        file_path: Path to the uploaded file

    Returns:
        Best-matching adapter instance, or None if no match above threshold
    """
    if not file_path.exists():
        return None

    best_adapter = None
    best_confidence = 0.5  # Minimum threshold

    for name, cls in _ADAPTERS.items():
        try:
            instance = cls()
            confidence = instance.detect(file_path)
            if confidence > best_confidence:
                best_confidence = confidence
                best_adapter = instance
                logger.debug("ERP detect: %s scored %.2f for %s", name, confidence, file_path.name)
        except Exception as exc:
            logger.debug("ERP detect: %s failed for %s: %s", name, file_path.name, exc)

    if best_adapter:
        logger.info("Detected ERP: %s (confidence=%.2f) for %s",
                     best_adapter.system_name, best_confidence, file_path.name)

    return best_adapter
