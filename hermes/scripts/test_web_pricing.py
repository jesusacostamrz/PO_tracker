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
        self.must_contain = []
    def web_search(self, prompt, country="MX", must_contain=None):
        self.queries.append(prompt)
        self.must_contain.append(must_contain)
        return {"text": "- Rodamiento 6204-2RS | $85 MXN | https://example.com/p/6204",
                "sources": ["https://example.com/p/6204"]}
    def image_urls(self, query, country="MX", limit=8):
        self.queries.append(query)
        # first hit is an unrelated lookalike (brand-word match) -> must be skipped;
        # second mentions the part but downloads will fail offline -> None overall
        return [{"url": "https://bad.example/x.jpg", "title": "NITRA fertilizante 50kg",
                 "link": "https://bad.example/fertilizante"},
                {"url": "https://good.example/6204.jpg", "title": "Rodamiento 6204-2RS",
                 "link": "https://good.example/p/6204-2rs"}]

serper = StubSerper()
offer = research_price(line, StubLLM({"price": 85.0, "currency": "MXN", "vendor": "X",
                                       "url": "https://example.com/p/6204", "note": ""}), serper)
assert offer is not None and offer["price"] == 85.0
assert serper.queries == ["6204-2RS"], serper.queries  # bare part number, no extra words
assert serper.must_contain == ["6204-2RS"]  # results pre-filtered to the exact part
print("OK research_price serper plain query + must_contain")

assert find_image_bytes("6204-2RS", "", "Rodamiento sellado", serper) is None
assert serper.queries[-1] == "6204-2RS"
print("OK find_image_bytes serper image path (lookalike hit filtered)")

# the must_contain filter itself (no network: feed _post results via monkeypatch)
from connectors.serper_client import SerperClient, norm_token
assert norm_token("BFRHP-38N") == "bfrhp38n"
sc = SerperClient("k")
sc._post = lambda url, q, c, n: {"organic": [
    {"title": "Nutrimon NITRA.SAM 28-4-0-6(S) 50 Kg", "snippet": "fertilizante", "link": "https://tierragro.com/x"},
    {"title": "bfrhp-38n - Pneumatic Threaded Fitting", "snippet": "NITRA recessed hex plug", "link": "https://automationdirect.com/bfrhp-38n"},
]}
r = sc.web_search("BFRHP-38N NITRA precio comprar", must_contain="BFRHP-38N")
assert r["sources"] == ["https://automationdirect.com/bfrhp-38n"], r
r_all = sc.web_search("BFRHP-38N NITRA precio comprar")
assert len(r_all["sources"]) == 2  # no filter -> both kept
print("OK serper must_contain drops wrong-product hits")

# US-locale fallback when MX-localized Google has nothing for the part
class StubSerperUSOnly:
    kind = "serper"
    def __init__(self):
        self.countries = []
    def web_search(self, prompt, country="MX", must_contain=None):
        self.countries.append(country)
        if country == "MX":
            return None
        return {"text": "- BFMC-38N Pneumatic Fitting | $14.50 | https://automationdirect.com/bfmc-38n",
                "sources": ["https://automationdirect.com/bfmc-38n"]}

us = StubSerperUSOnly()
offer = research_price({"part_number": "BFMC-38N", "description": "", "manufacturer": "", "quantity": 1},
                       StubLLM({"price": 14.5, "currency": "USD", "vendor": "AutomationDirect",
                                "url": "https://automationdirect.com/bfmc-38n", "note": ""}), us)
assert offer is not None and offer["price"] == 14.5
assert us.countries == ["MX", "US"], us.countries
print("OK research_price US fallback when MX empty")

# page_url short-circuit: a validated price-research page is used before any search
import core.product_images as pi
pi._try_page = lambda url: b"IMG" if url == "https://good.example/p/6204-2rs" else None
assert pi.find_image_bytes("6204-2RS", "", "", None, page_url="https://good.example/p/6204-2rs") == b"IMG"
assert pi.find_image_bytes("6204-2RS", "", "", None, page_url="https://dead.example/x") is None
print("OK find_image_bytes page_url first, no search needed")

print("ALL OK")
