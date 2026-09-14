"""Optional local transcription adapter.

The core engine stays dependency-free. If faster-whisper is installed, this
module creates segment and word timestamps locally; no cloud API is used.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def transcribe(audio: str | Path, model: str = "small", language: str | None = None,
               output: str | Path | None = None, device: str = "auto") -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Local transcription requires faster-whisper. Install it with "
            "'pip install faster-whisper'. No cloud API is used."
        ) from exc

    if device == "auto":
        try:
            import torch  # type: ignore
            has_cuda = bool(torch.cuda.is_available())
        except Exception:
            has_cuda = False
        device = "cuda" if has_cuda else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    segments, info = whisper.transcribe(
        str(audio), language=language, word_timestamps=True,
        vad_filter=True, beam_size=5,
    )

    rows: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    for segment in segments:
        rows.append({
            "id": len(rows),
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
            "text": segment.text.strip(),
        })
        for word in segment.words or []:
            words.append({
                "start": round(float(word.start), 3),
                "end": round(float(word.end), 3),
                "text": word.word.strip(),
                "probability": round(float(word.probability), 4),
            })

    result = {
        "audio": str(audio),
        "model": model,
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "segments": rows,
        "words": words,
    }
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language")
    parser.add_argument("--output", default="transcript.json")
    args = parser.parse_args()
    transcribe(args.audio, args.model, args.language, args.output)
