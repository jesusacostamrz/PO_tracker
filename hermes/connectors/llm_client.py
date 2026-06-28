"""Provider-agnostic LLM client (OpenAI-compatible).

Works with OpenAI **or** GLM/Zhipu by setting ``base_url`` + ``model`` in config/.env.
Used for: structured PO extraction, fuzzy-match reasoning, and drafting emails/notes.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class LLMClient:
    api_key: str
    base_url: str
    model: str
    vision_model: str | None = None

    def __post_init__(self):
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url or None)

    def chat(self, system: str, user: str, model=None, temperature=0.0, max_tokens=2000) -> str:
        resp = self._client.chat.completions.create(
            model=model or self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def chat_json(self, system: str, user: str, model=None, temperature=0.0, max_tokens=2000) -> dict:
        """Chat and parse a JSON object reply (uses response_format when the provider supports it)."""
        base = dict(
            model=model or self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        try:
            resp = self._client.chat.completions.create(response_format={"type": "json_object"}, **base)
        except Exception:
            resp = self._client.chat.completions.create(**base)  # provider lacks response_format
        return _loads(resp.choices[0].message.content or "")

    def vision_json(self, system: str, user_text: str, image_data_urls: list[str],
                    model=None, temperature=0.0, max_tokens=3000) -> dict:
        """Vision call for scanned/image POs. image_data_urls = ['data:image/png;base64,...']."""
        content = [{"type": "text", "text": user_text}]
        content += [{"type": "image_url", "image_url": {"url": u}} for u in image_data_urls]
        resp = self._client.chat.completions.create(
            model=model or self.vision_model or self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": content}],
        )
        return _loads(resp.choices[0].message.content or "")

    @classmethod
    def from_config(cls, cfg: dict) -> "LLMClient":
        llm = cfg["llm"]
        key = os.environ.get(llm["api_key_env"], "")
        if not key:
            raise RuntimeError(f"Missing {llm['api_key_env']} in .secrets/.env")
        return cls(key, llm.get("base_url", ""), llm["model"], llm.get("vision_model"))


def _loads(text: str) -> dict:
    """Tolerant JSON parse: strips ``` fences and pulls the first {...} if needed."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise
