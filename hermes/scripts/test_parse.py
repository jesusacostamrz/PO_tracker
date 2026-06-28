"""Parse a PO PDF and print the extracted JSON.

Usage:  python scripts/test_parse.py <path-to-po.pdf>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402
from core.po_parser import parse_po  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/test_parse.py <path-to-po.pdf>")
        return 2
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"not found: {pdf_path}")
        return 2

    cfg = load_config()
    try:
        llm = LLMClient.from_config(cfg)
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return 1

    data = parse_po(pdf_path.read_bytes(), llm, cfg.get("company", {}))
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
