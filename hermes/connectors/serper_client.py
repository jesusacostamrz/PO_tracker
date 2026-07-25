"""Google search via serper.dev — preferred retrieval for price research and
product images when ``SERPER_API_KEY`` is set.

Why: Google ranks the exact-SKU product page first, where LLM-native web search
(SearchClient) often surfaces lookalike parts. Same result shape as
``SearchClient.web_search`` so core code can hold either client; callers branch
on ``kind == "serper"`` only where the query must be a plain search string
instead of a prose instruction. Self-disables (``from_config`` returns ``None``)
without the key — no new hard dependency.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

_SEARCH_URL = "https://google.serper.dev/search"
_IMAGES_URL = "https://google.serper.dev/images"


@dataclass
class SerperClient:
    api_key: str
    kind = "serper"  # class attr, not a dataclass field

    @classmethod
    def from_config(cls, cfg: dict) -> "SerperClient | None":
        env = cfg.get("serper", {}).get("api_key_env", "SERPER_API_KEY")
        key = os.environ.get(env, "")
        return cls(key) if key else None

    def _post(self, url: str, query: str, country: str, num: int) -> dict:
        body = json.dumps({"q": query, "gl": country.lower(), "hl": "es", "num": num}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def web_search(self, query: str, country: str = "MX") -> dict | None:
        """Plain Google search. Returns {'text': str, 'sources': [url,...]} or None."""
        try:
            data = self._post(_SEARCH_URL, query, country, 10)
        except Exception as e:
            print(f"WARN serper_client: {e}")
            return None
        lines: list[str] = []
        sources: list[str] = []
        for r in data.get("organic", []) or []:
            link = r.get("link") or ""
            price = r.get("price") or (r.get("attributes") or {}).get("price") or ""
            lines.append(f"- {r.get('title', '')} | {r.get('snippet', '')} {price} | {link}".strip())
            if link and link not in sources:
                sources.append(link)
        if not lines:
            return None
        return {"text": "\n".join(lines), "sources": sources}

    def image_urls(self, query: str, country: str = "MX", limit: int = 5) -> list[str]:
        """Direct image URLs from Google Images, best-ranked first."""
        try:
            data = self._post(_IMAGES_URL, query, country, limit)
        except Exception as e:
            print(f"WARN serper_client: {e}")
            return []
        return [i["imageUrl"] for i in (data.get("images") or [])[:limit] if i.get("imageUrl")]
