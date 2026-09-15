#!/usr/bin/env python3
"""Turn collected research into a source-grounded evidence pack.

Two grounding methods:
  * ollama   — a local Ollama-compatible LLM curates claims/importance/tags and
               every output is gate-checked against the researched source URLs.
               The research pack is chunked and each prompt/response is strictly
               bounded so CPU-only models finish inside the HTTP timeout.
  * deterministic-source-extraction — used automatically when the local model is
               unavailable (or with --no-llm): every claim is a verbatim sentence
               drawn from a researched source, so nothing is ever invented.

The grounding method and its note are written into the evidence pack and
forwarded to the production manifest.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.grounding import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_EVIDENCE,
    DEFAULT_MAX_SOURCES,
    DEFAULT_MAX_TEXT_CHARS,
    DEFAULT_NUM_PREDICT,
    GroundingFailed,
    GroundingUnavailable,
    chunked,
    compact_sources,
    extract,
    merge_evidence,
    title_and_thesis,
)
from engine.local_llm import generate_json

PROMPT = """
You are the research editor for a technology documentary. Produce ONLY a JSON object.
Every factual claim must be directly supported by one of the supplied sources.
Never invent numbers, dates, names, quotes, causality or conclusions.
Do not use a search snippet when extracted source text is available.
Prefer primary sources, company filings, government material, academic papers and reputable reporting.
Mark importance high only when it is central to the thesis.
Return the evidence for the sources below, using only the SOURCE uris listed.
Return ONLY this schema:
{{"evidence":[{{"claim":"...","source":"<uri above>","source_type":"article|primary|paper|filing|interview|other","importance":"high|normal","tags":["..."],"quote":"<short exact quote from that source's text>"}}]}}

TOPIC: {topic}

{blocks}
"""


def _known_sources(research: dict[str, Any]) -> set[str]:
    return {str(row.get("url")) for row in research.get("sources", [])}


def _gate_evidence(pack: dict[str, Any], research: dict[str, Any]) -> None:
    """Hard safety gate: every evidence item must cite a researched source."""
    known = _known_sources(research)
    if not isinstance(pack, dict) or "evidence" not in pack:
        raise GroundingFailed("Local model returned an invalid evidence schema")
    for item in pack.get("evidence", []):
        if str(item.get("source")) not in known:
            raise GroundingFailed(f"Grounding gate failed: unknown source {item.get('source')}")
        if not item.get("quote"):
            raise GroundingFailed(f"Grounding gate failed: missing supporting quote for {item.get('id')}")


def _llm_pack(research: dict[str, Any], *, model: str, endpoint: str,
              max_sources: int, max_text_chars: int, chunk_size: int,
              max_evidence: int, num_predict: int) -> dict[str, Any]:
    """Bounded, chunked LLM grounding.

    The full research pack can be tens of kilobytes, which a CPU-only model must
    both prefill and emit against. Each source is compacted to a strict text
    budget and sources are grounded a few at a time, so every prompt and every
    response is small enough to finish comfortably inside the HTTP timeout.
    """
    sources = compact_sources(research, max_sources=max_sources, max_text_chars=max_text_chars)
    chunks = chunked(sources, chunk_size=chunk_size)
    if not chunks:
        raise GroundingFailed("No research sources to ground")
    topic = str(research.get("topic") or "").strip()
    parts: list[dict[str, Any]] = []
    used: list[str] = []
    for chunk in chunks:
        blocks = "\n\n".join(
            f"SOURCE {pos}\nuri: {s['url']}\ntitle: {s['title']}\ntext: {s['text']}"
            for pos, s in enumerate(chunk, start=1))
        result = generate_json(PROMPT.format(topic=topic, blocks=blocks), model=model,
                               endpoint=endpoint,
                               options={"temperature": 0.0, "num_predict": num_predict})
        _gate_evidence(result, {"sources": chunk})
        parts.append(result)
        used += [s["url"] for s in chunk]
    evidence = merge_evidence(parts, max_evidence=max_evidence)
    if not evidence:
        raise GroundingFailed(
            "Local model produced no supported evidence from any researched source")
    title, thesis = title_and_thesis(research, evidence)
    pack = {"title": title, "thesis": thesis, "evidence": evidence}
    _gate_evidence(pack, research)
    pack["grounding"] = {
        "method": "ollama",
        "model": model,
        "endpoint": endpoint,
        "chunk_count": len(chunks),
        "source_text_budget": max_text_chars,
        "num_predict_budget": num_predict,
        "sources_total": len(research.get("sources", [])),
        "sources_used": used,
        "evidence_count": len(evidence),
        "note": ("Claims were generated by a local LLM over bounded, chunked "
                 "source passages and gate-checked against the researched source "
                 "URLs."),
    }
    return pack


def ground(research: dict[str, Any], out: str | Path, *, model: str = "llama3.2",
           endpoint: str = "http://127.0.0.1:11434/api/generate",
           require_llm: bool = False, use_llm: bool = True,
           max_sources: int = DEFAULT_MAX_SOURCES,
           max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
           chunk_size: int = DEFAULT_CHUNK_SIZE,
           max_evidence: int = DEFAULT_MAX_EVIDENCE,
           num_predict: int = DEFAULT_NUM_PREDICT) -> dict[str, Any]:
    """Produce a verified evidence pack from research, preferring the local LLM."""
    pack: dict[str, Any] | None = None
    if use_llm:
        try:
            pack = _llm_pack(research, model=model, endpoint=endpoint,
                             max_sources=max_sources, max_text_chars=max_text_chars,
                             chunk_size=chunk_size, max_evidence=max_evidence,
                             num_predict=num_predict)
        except GroundingUnavailable as exc:
            if require_llm:
                raise GroundingFailed(
                    f"Committed to LLM grounding (--require-llm) but the local model is "
                    f"unavailable at {endpoint}: {exc}") from exc
            print(f"LLM grounding unavailable ({exc}); using deterministic "
                  "source-grounded extraction (verbatim claims).", file=sys.stderr)
    if pack is None:
        pack = extract(research)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    print(target)
    return pack


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("research_json")
    p.add_argument("--out", default="projects/evidence.generated.json")
    p.add_argument("--model", default="llama3.2")
    p.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
    p.add_argument("--require-llm", action="store_true",
                   help="Fail instead of using the deterministic fallback when the LLM is unreachable")
    p.add_argument("--no-llm", action="store_true",
                   help="Skip the LLM entirely and use deterministic verbatim-source extraction")
    p.add_argument("--num-predict", type=int, default=DEFAULT_NUM_PREDICT,
                   help="Per-chunk Ollama token budget (bounded output on slow CPUs)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                   help="Sources grounded per LLM call")
    a = p.parse_args()
    research = json.loads(Path(a.research_json).read_text(encoding="utf-8"))
    ground(research, a.out, model=a.model, endpoint=a.endpoint,
           require_llm=a.require_llm, use_llm=not a.no_llm,
           chunk_size=a.chunk_size, num_predict=a.num_predict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())