"""Load unicontrol.config.yaml, resolve ${ENV_VAR} from .secrets/.env, and make the
sibling ``hermes/`` package importable so we can reuse its connectors.

Mirrors hermes/core/config.py. `add_hermes_to_path()` puts the Hermes repo root on
sys.path so `from connectors.odoo_client import OdooClient` resolves.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv optional; env vars can also be set by the OS / systemd
    load_dotenv = None

_UC_ROOT = Path(__file__).resolve().parents[2]          # Unicontrol/
_HERMES_ROOT = _UC_ROOT.parent / "hermes"               # sibling hermes/
_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def add_hermes_to_path() -> None:
    """Put the sibling hermes/ repo root on sys.path (for reused connectors)."""
    p = str(_HERMES_ROOT)
    if _HERMES_ROOT.exists() and p not in sys.path:
        sys.path.insert(0, p)


def load_config(config_path: str | None = None, env_path: str | None = None) -> dict:
    cfg_path = Path(config_path) if config_path else _UC_ROOT / "config" / "unicontrol.config.yaml"
    secrets_env = Path(env_path) if env_path else _UC_ROOT / ".secrets" / ".env"
    if load_dotenv and secrets_env.exists():
        load_dotenv(secrets_env)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return _resolve(raw)


def secret(name: str, required: bool = True) -> str:
    val = os.environ.get(name, "")
    if required and not val:
        raise RuntimeError(f"Missing required secret '{name}'. Add it to Unicontrol/.secrets/.env")
    return val


def _resolve(obj):
    if isinstance(obj, dict):
        return {k: _resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve(v) for v in obj]
    if isinstance(obj, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    return obj
