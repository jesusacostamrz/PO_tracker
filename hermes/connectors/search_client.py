"""Web search via OpenAI's built-in ``web_search`` tool (Responses API).

OpenAI-only: the ``web_search`` tool has no equivalent on GLM/Zhipu or other
OpenAI-compatible providers, so this connector is optional and self-disables
(``from_config`` returns ``None``) whenever the configured LLM isn't OpenAI.
No new secret — rides the existing ``LLM_API_KEY``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass
class SearchClient:
    api_key: str
    model: str

    @classmethod
    def from_config(cls, cfg: dict) -> "SearchClient | None":
        llm = cfg.get("llm", {})
        key = os.environ.get(llm.get("api_key_env", ""), "")
        base_url = llm.get("base_url", "") or ""
        if not key or (base_url and "api.openai.com" not in base_url):
            return None
        return cls(key, llm.get("model", "gpt-4o-mini"))

    def web_search(self, prompt: str, country: str = "MX") -> dict | None:
        """Run one web_search call. Returns {'text': str, 'sources': [url,...]} or None."""
        try:
            return self._call(self.model, "web_search", prompt, country)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 400 and "web_search" in body:
                try:
                    return self._call(self.model, "web_search_preview", prompt, country)
                except Exception as e2:
                    print(f"WARN search_client: web_search_preview retry failed: {e2}")
                    return None
            if e.code == 400 and ("model" in body or self.model in body):
                try:
                    return self._call("gpt-4o", "web_search", prompt, country)
                except Exception as e2:
                    print(f"WARN search_client: gpt-4o retry failed: {e2}")
                    return None
            print(f"WARN search_client: HTTP {e.code}: {body[:300]}")
            return None
        except Exception as e:
            print(f"WARN search_client: {e}")
            return None

    def _call(self, model: str, tool_type: str, prompt: str, country: str) -> dict:
        body = json.dumps({
            "model": model,
            "tools": [{"type": tool_type, "user_location": {"type": "approximate", "country": country}}],
            "input": prompt,
        }).encode("utf-8")
        req = urllib.request.Request(
            _RESPONSES_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        texts: list[str] = []
        sources: list[str] = []
        for item in data.get("output", []) or []:
            if item.get("type") != "message":
                continue
            for part in item.get("content", []) or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
                    for ann in part.get("annotations", []) or []:
                        if ann.get("type") == "url_citation":
                            url = ann.get("url")
                            if url and url not in sources:
                                sources.append(url)
        return {"text": "\n".join(texts), "sources": sources}
