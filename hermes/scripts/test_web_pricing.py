"""Offline self-check for web_pricing / product_images. No network, no creds."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.web_pricing import research_price
from core.product_images import _og_image_url, find_image_bytes


class StubSearch:
    def web_search(self, prompt, country="MX"):
        return {"text": "Rodamiento 6204-2RS, $85.00 MXN, Proveedor Ejemplo, https://example.com/p/6204",
                "sources": ["https://example.com/p/6204"]}


class StubLLM:
    def __init__(self, offer):
        self._offer = offer

    def chat_json(self, system, user, max_tokens=400):
        return self._offer


line = {"part_number": "6204-2RS", "description": "Rodamiento sellado", "manufacturer": "", "quantity": 12}

offer = research_price(line, StubLLM({"price": 85.0, "currency": "MXN", "vendor": "Proveedor Ejemplo",
                                       "url": "https://example.com/p/6204", "note": ""}), StubSearch())
assert offer is not None and isinstance(offer["price"], float) and offer["price"] == 85.0
print("OK research_price stubbed offer")

assert research_price(line, StubLLM({}), None) is None
print("OK research_price None search")

# null price now degrades to a reference-link-only suggestion (price None, url kept)
ref = research_price(line, StubLLM({"price": None}), StubSearch())
assert ref is not None and ref["price"] is None and ref["url"] == "https://example.com/p/6204"
print("OK research_price null price -> reference link")

html_og = '<html><head><meta property="og:image" content="https://example.com/img/6204.jpg"></head></html>'
assert _og_image_url(html_og) == "https://example.com/img/6204.jpg"
print("OK _og_image_url og:image")

html_twitter = '<html><head><meta name="twitter:image" content="https://example.com/img/tw.jpg"></head></html>'
assert _og_image_url(html_twitter) == "https://example.com/img/tw.jpg"
print("OK _og_image_url twitter:image")

html_content_first = '<html><head><meta content="https://example.com/img/first.jpg" property="og:image"></head></html>'
assert _og_image_url(html_content_first) == "https://example.com/img/first.jpg"
print("OK _og_image_url content-attribute-first")

html_ldjson = '<html><script type="application/ld+json">{"@type":"Product","image": ["https://example.com/img/ld.jpg"]}</script></html>'
assert _og_image_url(html_ldjson) == "https://example.com/img/ld.jpg"
print("OK _og_image_url json-ld fallback")

assert find_image_bytes("6204-2RS", "", "Rodamiento sellado", None) is None
print("OK find_image_bytes None search")


# --- serper path: plain query built from the part, same result shape ---
class StubSerper:
    kind = "serper"
    def __init__(self):
        self.queries = []
    def web_search(self, prompt, country="MX"):
        self.queries.append(prompt)
        return {"text": "- Rodamiento 6204-2RS | $85 MXN | https://example.com/p/6204",
                "sources": ["https://example.com/p/6204"]}
    def image_urls(self, query, country="MX", limit=5):
        self.queries.append(query)
        return []  # empty -> find_image_bytes degrades to None, no scraping attempted

serper = StubSerper()
offer = research_price(line, StubLLM({"price": 85.0, "currency": "MXN", "vendor": "X",
                                       "url": "https://example.com/p/6204", "note": ""}), serper)
assert offer is not None and offer["price"] == 85.0
assert serper.queries == ["6204-2RS precio comprar"], serper.queries  # plain query, not prose prompt
print("OK research_price serper plain query")

assert find_image_bytes("6204-2RS", "", "Rodamiento sellado", serper) is None
assert serper.queries[-1] == "6204-2RS"
print("OK find_image_bytes serper image path")

print("ALL OK")
