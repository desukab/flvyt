"""Caption timing utilities shared by the renderer and delivery pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def words_to_srt(words: list[dict[str, Any]], output: str | Path,
                 max_words: int = 7, max_duration: float = 2.2,
                 offset: float = 5.0) -> Path:
    """Write readable captions and account for FLVYT's five-second intro."""
    rows: list[tuple[float, float, str]] = []
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
        boundary = len(current) >= max_words or (end - start) >= max_duration
        if boundary:
            rows.append((start, end, " ".join(current)))
            current, start, end = [], None, None
    if current and start is not None and end is not None:
        rows.append((start, end, " ".join(current)))

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for i, (start, end, text) in enumerate(rows, 1):
            fh.write(f"{i}\n{_time(start)} --> {_time(end)}\n{text}\n\n")
    return path


def write_caption_json(words: list[dict[str, Any]], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"words": words}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
