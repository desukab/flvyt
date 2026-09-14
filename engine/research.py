"""Zero-API research collector.

This module discovers candidate sources and extracts their readable text. It does
not turn search snippets into facts: source verification remains explicit in the
evidence-pack step so the production pipeline does not manufacture claims.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def collect(topic: str, output: str | Path, max_results: int = 12) -> Path:
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise RuntimeError("Install research helpers with: pip install -r requirements-research.txt") from exc

    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError("Install research helpers with: pip install -r requirements-research.txt") from exc

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in DDGS().text(topic, region="wt-wt", safesearch="moderate", max_results=max_results):
        url = str(row.get("href") or row.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        text = ""
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_comments=False) or ""
        except Exception:
            text = ""
        results.append({
            "title": row.get("title", ""),
            "url": url,
            "snippet": row.get("body", ""),
            "text": text[:20000],
        })

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"topic": topic, "sources": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
