"""Deterministic, source-grounded evidence extraction from collected research.

When no local LLM is available, research must still turn into a verified
evidence pack without inventing anything. This module extracts each evidence
item as a verbatim sentence from the researched source text (with a snippet
fallback when extraction failed), so the claim and its supporting quote are
literally what the source said. Nothing is generated, summarized or paraphrased.

The alternate (better-curated) path uses an Ollama-compatible local LLM and
remains an optional enhancement; the grounding method is recorded in the
evidence pack and surfaced in the production manifest.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class GroundingUnavailable(Exception):
    """The configured local LLM could not be reached or produced no answer."""


class GroundingFailed(Exception):
    """Grounding could not produce a verified, source-grounded evidence pack."""


STOP = frozenset(
    "the and for are was were with from that this these those which have has had "
    "will would could should about their there here then than your you its it they "
    "them what when where why how not but also into over under after before while "
    "because against each other some such only very much more most been being off "
    "out on in at by of or as an is to a".split()
)


def _topic_tokens(topic: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{4,}", topic.lower()) if t not in STOP}


BOILERPLATE = (
    "cookie", "subscribe", "sign up", "newsletter", "privacy policy", "terms of",
    "copyright", "all rights reserved", "read more", "menu", "download the app",
    "advertisement", "sponsored", "share this", "comment", "©", "skip to",
    "we use cookies", "to provide you with a better",
)

PRONOUN_STARTERS = frozenset(
    "this it they them these those that he she we you i there here so also but "
    "and then however moreover although because since".split()
)


def _key(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.lower()).strip().rstrip(".")


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=['\"(]?[A-Z0-9])", cleaned)
    return [p.strip().strip("\"“”") for p in parts if p.strip()]


def _boilerplate(sentence: str) -> bool:
    low = sentence.lower()
    return any(token in low for token in BOILERPLATE)


def score(sentence: str, tokens: set[str]) -> float:
    """Rank how well a sentence can stand alone as a supported documentary claim."""
    low = sentence.lower()
    if len(sentence) < 12 or len(sentence) > 300:
        return -1.0
    if _boilerplate(sentence):
        return -2.0
    if not any(ch.isalnum() for ch in sentence):
        return -2.0
    value = min(2.0, len(sentence) / 60.0)
    if re.search(r"\d", sentence):
        value += 1.0
    value += 1.5 * sum(1 for token in tokens if token in low)
    words = low.split()
    first = words[0].strip("(\"'")
    if first in PRONOUN_STARTERS:
        value -= 1.2
    if sentence.count("(") != sentence.count(")"):
        value -= 1.0
    return value


def pick(sentences: list[str], tokens: set[str]) -> str | None:
    best: str | None = None
    best_score = -1.0
    for sentence in sentences:
        value = score(sentence, tokens)
        if value > best_score:
            best, best_score = sentence, value
    return best if best_score > 0.0 else None


def source_type_for(url: str) -> str:
    low = str(url).lower()
    if "wikipedia" in low:
        return "article"
    if ".gov" in low or "nasa" in low:
        return "filing"
    if ".edu" in low or "arxiv" in low:
        return "paper"
    if "interview" in low or "podcast" in low:
        return "interview"
    return "article"


def extract(research: dict[str, Any], *, max_items: int = 12,
            max_claim_chars: int = 280) -> dict[str, Any]:
    """Build a verified evidence pack from researched source material.

    Every claim is a verbatim sentence drawn directly from a source's extracted
    text (or its search snippet when extraction produced nothing), so nothing is
    ever fabricated. Sources that yield no usable sentence are recorded, not
    silently dropped.
    """
    topic = str(research.get("topic") or "").strip()
    tokens = _topic_tokens(topic)
    evidence: list[dict[str, Any]] = []
    used: list[str] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in research.get("sources", []):
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        text = str(row.get("text") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        sentences = split_sentences(text) if text else split_sentences(snippet)
        candidates = [s for s in sentences if _key(s) not in seen]
        chosen = pick(candidates, tokens)
        if chosen is None:
            reason = "no usable source sentence extracted"
            if not sentences:
                reason = "no usable source sentence extracted"
            elif candidates:
                reason = "no source sentence scored high enough to stand alone"
            skipped.append({"url": url, "reason": reason})
            continue
        seen.add(_key(chosen))
        used.append(url)
        if len(evidence) >= max_items:
            break
        sentence = chosen if len(chosen) <= max_claim_chars else chosen[:max_claim_chars]
        evidence.append({
            "id": f"e{len(evidence) + 1:02d}",
            "claim": sentence,
            "source": url,
            "source_type": source_type_for(url),
            "importance": "high" if not evidence else "normal",
            "tags": [],
            "quote": sentence,
        })

    if not evidence:
        raise GroundingFailed(
            "No extractable source material was found; cannot ground evidence without "
            "source text. Re-run research, or install and start a local Ollama model "
            "for the LLM grounding path.")

    return {
        "title": topic or "Untitled Documentary",
        "thesis": evidence[0]["claim"],
        "evidence": evidence,
        "grounding": {
            "method": "deterministic-source-extraction",
            "engine": "engine.grounding.extract",
            "note": "No LLM was used. Every claim is a verbatim sentence from a "
                    "supplied source; nothing was generated or invented.",
            "sources_used": used,
            "sources_skipped": skipped,
            "evidence_count": len(evidence),
        },
    }


DEFAULT_MAX_SOURCES = 8
DEFAULT_MAX_TEXT_CHARS = 1200
DEFAULT_CHUNK_SIZE = 4
DEFAULT_MAX_EVIDENCE = 12
DEFAULT_NUM_PREDICT = 600


def compact_sources(research: dict[str, Any], *, max_sources: int = DEFAULT_MAX_SOURCES,
                    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS) -> list[dict[str, Any]]:
    """A bounded, ordered view of research that is safe to embed in an LLM prompt.

    Full research packs can exceed 20K tokens once long-extraction text is
    included; sending them unbounded stalls CPU-only models past any practical
    timeout. This keeps per-source text within a strict budget (snippet fallback
    when extraction produced nothing) so prefill stays seconds, not minutes.
    """
    rows: list[dict[str, Any]] = []
    for row in research.get("sources", []):
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            text = str(row.get("snippet") or "").strip()
        rows.append({
            "url": url,
            "title": str(row.get("title") or "").strip()[:160],
            "text": text[:max_text_chars],
        })
        if len(rows) >= max_sources:
            break
    return rows


def chunked(rows: list[dict[str, Any]], *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[list[dict[str, Any]]]:
    """Split compact sources into small, ordered groups for one LLM call each."""
    return [rows[i:i + chunk_size] for i in range(0, len(rows), chunk_size)]


def merge_evidence(parts: list[dict[str, Any]], *, max_evidence: int = DEFAULT_MAX_EVIDENCE) -> list[dict[str, Any]]:
    """Merge per-chunk LLM evidence into a deterministic, deduplicated evidence list.

    Ids are renumbered in source-first order, duplicate claims are dropped, and
    importance/tags are normalized so identical research always yields an
    identical pack shape (filenames, ids, ordering).
    """
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in parts:
        for item in part.get("evidence") or [] if isinstance(part, dict) else []:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            source = str(item.get("source") or "").strip()
            if not claim or not source:
                continue
            key = _key(claim)
            if key in seen:
                continue
            seen.add(key)
            importance = item.get("importance")
            evidence.append({
                "id": f"e{len(evidence) + 1:02d}",
                "claim": claim,
                "source": source,
                "source_type": str(item.get("source_type") or "article").strip(),
                "importance": importance if importance in {"high", "normal"} else "normal",
                "tags": list(item.get("tags") or [])[:8],
                "quote": str(item.get("quote") or "").strip(),
            })
            if len(evidence) >= max_evidence:
                return evidence
    return evidence


def title_and_thesis(research: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[str, str]:
    """Derive the pack title/thesis deterministically instead of spending an LLM call."""
    title = str(research.get("topic") or "").strip() or "Untitled Documentary"
    thesis = next((e["claim"] for e in evidence if e["importance"] == "high"), None)
    if not thesis and evidence:
        thesis = evidence[0]["claim"]
    return title, thesis or ""


def attach_provenance(project_path: str | Path, provenance: dict[str, Any]) -> Path:
    """Write grounding provenance into a planned project file for the manifest."""
    path = Path(project_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["provenance"] = provenance
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path