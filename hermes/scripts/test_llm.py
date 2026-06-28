"""LLM connectivity check (provider-agnostic: OpenAI or GLM/Zhipu).

Verifies the API key + base_url + model by making one tiny chat call. Prints the
configured endpoint/model and the model's reply. Costs only a few tokens.

Run:  python scripts/test_llm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402


def main() -> int:
    cfg = load_config()
    llm = cfg["llm"]
    print(f"base_url    : {llm.get('base_url') or '(OpenAI default)'}")
    print(f"model       : {llm.get('model') or '(unset)'}")
    print(f"vision_model: {llm.get('vision_model') or '(unset)'}")

    try:
        client = LLMClient.from_config(cfg)
    except RuntimeError as exc:
        print(f"\nFAILED: {exc}")
        return 1

    try:
        reply = client.chat_json(
            system='You are a connectivity probe. Reply with ONLY this JSON: {"status":"ok"}',
            user="ping",
            max_tokens=50,
        )
        print(f"\nModel reply: {reply}")
        print("\nOK — LLM text path works.")
        return 0
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        print("(Check LLM_API_KEY, LLM_BASE_URL, and that LLM_MODEL is a valid model name for your provider.)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
