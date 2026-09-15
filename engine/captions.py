"""Caption timing utilities shared by the renderer and delivery pipeline.

Captions are grouped into readable phrases from per-word timestamps, honor the
documentary's intro offset, wrap at word boundaries to stay inside safe margins,
and emphasise high-signal tokens (numbers, units, acronyms) so viewers can
follow the argument without backing it away from the picture.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

INTRO_SECONDS = 5.0
MAX_WORDS = 7
MAX_DURATION = 2.6
MAX_CHARS_PER_LINE = 42

SENTENCE_END = re.compile(r"[.!?…]$")
EMPHASIS_TOKEN = re.compile(
    r"(?<!\w)(?:(?:\$|€|£|¥)?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|million|billion|"
    r"trillion|nm|mm|km|GHz|MHz|GB|TB|GW|MW|years|year)?|[A-Z][A-Z0-9]{2,})(?!\w)"
)


def _time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def emphasize(text: str) -> str:
    """Wrap high-signal tokens in SRT bold markup."""
    out: list[str] = []
    last = 0
    for match in EMPHASIS_TOKEN.finditer(text):
        out.append(text[last:match.start()])
        out.append(f"<b>{match.group()}</b>")
        last = match.end()
    out.append(text[last:])
    return "".join(out)


def _wrap(text: str, width: int = MAX_CHARS_PER_LINE) -> str:
    """Word-wrap to stay within safe margins, at most two balanced lines."""
    if len(text) <= width:
        return text
    words = text.split()
    best = min(range(1, len(words)), key=lambda i: abs(sum(len(w) for w in words[:i]) - sum(len(w) for w in words[i:])))
    return "\\N".join([" ".join(words[:best]), " ".join(words[best:])])


def words_to_cues(words: list[dict[str, Any]], offset: float = INTRO_SECONDS,
                  max_words: int = MAX_WORDS, max_duration: float = MAX_DURATION,
                  max_chars: int = MAX_CHARS_PER_LINE) -> list[dict[str, Any]]:
    """Group word timestamps into readable phrase cues.

    A cue breaks on sentence-final punctuation, word/character/duration budgets
    and soft punctuation, whichever comes first, so the text on screen advances
    with the argument rather than in fixed-width clumps.
    """
    rows: list[dict[str, Any]] = []
    current: list[str] = []
    start = end = None
    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        ws, we = float(word["start"]) + offset, float(word["end"]) + offset
        if start is None:
            start = ws
        current.append(text)
        end = we
        joined = " ".join(current)
        sentence_end = bool(SENTENCE_END.search(text))
        hard_boundary = (
            len(current) >= max_words
            or (end - start) >= max_duration
            or len(joined) >= max_chars * 2
        )
        if hard_boundary or sentence_end:
            rows.append({"start": round(start, 3), "end": round(end, 3), "text": joined})
            current, start, end = [], None, None
    if current and start is not None and end is not None:
        rows.append({"start": round(start, 3), "end": round(end, 3), "text": " ".join(current)})
    return rows


def words_to_srt(words: list[dict[str, Any]], output: str | Path,
                 max_words: int = MAX_WORDS, max_duration: float = MAX_DURATION,
                 max_chars: int = MAX_CHARS_PER_LINE, offset: float = INTRO_SECONDS,
                 bold_emphasis: bool = True) -> Path:
    """Write readable captions and account for FLVYT's five-second intro."""
    cues = words_to_cues(words, offset=offset, max_words=max_words,
                         max_duration=max_duration, max_chars=max_chars)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for i, cue in enumerate(cues, 1):
            text = _wrap(cue["text"], max_chars)
            if bold_emphasis:
                lines = [emphasize(line) for line in text.split("\\N")]
                text = "\\N".join(lines)
            fh.write(f"{i}\n{_time(cue['start'])} --> {_time(cue['end'])}\n{text}\n\n")
    return path


def write_caption_json(words: list[dict[str, Any]], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "words": words,
        "cues": words_to_cues(words),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path