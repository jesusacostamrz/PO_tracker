"""Best-effort product image lookup for auto-created products (via web search).

Finds a product page through SearchClient, then scrapes its og:image/twitter:image
meta tag and downloads it. Every step degrades to None on failure — an auto-created
product with no image is fine; a crash on intake is not.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from urllib.parse import urljoin

_UA = "Mozilla/5.0 (compatible; HermesBot/1.0)"
_MAX_PAGE_BYTES = 500_000
_MAX_IMAGE_BYTES = 3_000_000

# property/name and content may appear in either order, and as "property" or "name".
_META_RE = re.compile(
    r'<meta\s+[^>]*?(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*?content=["\']([^"\']+)["\']'
    r'|<meta\s+[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.IGNORECASE,
)


# fallbacks for pages without og:image: JSON-LD product schema, then <link rel=image_src>
_LDJSON_IMG_RE = re.compile(r'"image"\s*:\s*\[?\s*"(https?://[^"]+)"', re.IGNORECASE)
_LINK_IMG_RE = re.compile(
    r'<link\s+[^>]*?rel=["\']image_src["\'][^>]*?href=["\']([^"\']+)["\']', re.IGNORECASE)


def _og_image_url(html: str) -> str | None:
    m = _META_RE.search(html)
    if m:
        return m.group(1) or m.group(2)
    m = _LDJSON_IMG_RE.search(html) or _LINK_IMG_RE.search(html)
    return m.group(1) if m else None


def find_image_bytes(part_number: str, manufacturer: str, description: str, search,
                     page_url: str | None = None) -> bytes | None:
    # A page already validated for this exact part (e.g. the price-research
    # source) is the best image source — same product guaranteed, no extra
    # search call. Search engines below are the fallback.
    if page_url:
        data = _try_page(page_url)
        if data:
            return data
    if search is None:
        return None
    part = (part_number or "").strip()
    mfr = (manufacturer or "").strip()
    subject = f"{part} {mfr}".strip() if part else (description or "").strip()
    if not subject:
        return None

    if getattr(search, "kind", "") == "serper":
        # Google Images gives direct image URLs — no page scraping needed.
        # Only trust a hit whose title/source page mentions the part number:
        # brand words alone drag in unrelated products (wrong image is worse
        # than no image). No part number -> keep first-hit behavior.
        key = re.sub(r"[^a-z0-9]", "", part.lower())
        # bare part number query — brand/description words attract lookalikes;
        # MX first, US fallback (MX-localized Google lacks many US-catalog parts)
        for country in ("MX", "US"):
            for img in search.image_urls(part or subject, country=country):
                hay = re.sub(r"[^a-z0-9]", "", f"{img['title']} {img['link']}".lower())
                if key and key not in hay:
                    continue
                data = _download_image(img["url"])
                if data:
                    return data
        return None

    try:
        result = search.web_search(f"Pagina de producto para: {subject}", country="MX")
    except Exception as e:
        print(f"WARN product_images: search failed: {e}")
        return None
    if not result:
        return None

    for page_url in (result.get("sources") or [])[:3]:
        img_bytes = _try_page(page_url)
        if img_bytes:
            return img_bytes
    return None


def _try_page(page_url: str) -> bytes | None:
    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read(_MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    except Exception:
        return None

    img_url = _og_image_url(html)
    if not img_url:
        return None
    if img_url.startswith("//"):
        img_url = "https:" + img_url
    else:
        img_url = urljoin(page_url, img_url)
    return _download_image(img_url)


def _download_image(img_url: str) -> bytes | None:
    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return None
            data = resp.read(_MAX_IMAGE_BYTES + 1)
            if len(data) > _MAX_IMAGE_BYTES:
                return None
            return data
    except Exception:
        return None
