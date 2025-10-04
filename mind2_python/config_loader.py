# mind2_python/config_loader.py

import os
import yaml
import logging
from typing import Any, Dict

logger = logging.getLogger("ConfigLoader")
logger.setLevel(logging.INFO)
logger.propagate = True


def _deep_update(original: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    recursive merge dict
    """
    for k, v in (updates or {}).items():
        if isinstance(v, dict) and isinstance(original.get(k), dict):
            original[k] = _deep_update(original.get(k, {}), v)
        else:
            original[k] = v
    return original


def load_config(path: str = None, overrides: dict = None) -> Dict[str, Any]:
    """
    Load YAML config (default = config.symbols.yaml).
    Apply overrides if given.
    """
    cfg: Dict[str, Any] = {}

    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "config.symbols.yaml")

    path = os.path.abspath(path)

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            logger.info(f"[ConfigLoader] Loaded config: {path}")
        except Exception as e:
            logger.error(f"[ConfigLoader] Failed to load config {path}: {e}")
            cfg = {}
    else:
        logger.warning(f"[ConfigLoader] Config file not found: {path}")

    if overrides:
        cfg = _deep_update(cfg, overrides)
        logger.info(f"[ConfigLoader] Applied overrides: {overrides}")

    return cfg
