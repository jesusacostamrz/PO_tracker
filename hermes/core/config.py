"""Load hermes.config.yaml and resolve ${ENV_VAR} placeholders from .secrets/.env."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv optional; env vars can also be set by the OS / systemd
    load_dotenv = None

_ROOT = Path(__file__).resolve().parents[1]
_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_config(config_path: str | None = None, env_path: str | None = None) -> dict:
    """Return the parsed config with ${VAR} placeholders substituted from the environment."""
    cfg_path = Path(config_path) if config_path else _ROOT / "config" / "hermes.config.yaml"
    secrets_env = Path(env_path) if env_path else _ROOT / ".secrets" / ".env"

    if load_dotenv and secrets_env.exists():
        load_dotenv(secrets_env)

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return _resolve(raw)


def secret(name: str, required: bool = True) -> str:
    """Fetch a secret from the environment (loaded from .secrets/.env)."""
    val = os.environ.get(name, "")
    if required and not val:
        raise RuntimeError(
            f"Missing required secret '{name}'. Add it to .secrets/.env (see .env.example)."
        )
    return val


def _resolve(obj):
    if isinstance(obj, dict):
        return {k: _resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve(v) for v in obj]
    if isinstance(obj, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    return obj
