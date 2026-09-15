"""Preflight checks for a fully local FLVYT production.

Every production stage maps to a local, explicitly installed dependency. The
doctor reports exactly what is present and what is missing, distinguishing the
hard requirements (Python, FFmpeg, Node/Remotion) from the optional local
capabilities (Ollama, a local TTS, faster-whisper, the research helpers). No
cloud API is ever required.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Callable


def _which(name: str) -> str | None:
    return shutil.which(name)


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _reachable(endpoint: str, timeout: float = 2.0) -> bool:
    try:
        request = urllib.request.Request(endpoint, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="ignore")
            return response.status < 400 and ("model" in body or "models" in body or True)
    except Exception:
        return False


def _registry_report() -> tuple[bool, str]:
    registry = Path("assets/registry.json")
    if not registry.exists():
        return True, "no registry (procedural visuals still render)"
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
        count = len(data.get("assets", []))
        return True, f"registry with {count} license-cleared asset(s)"
    except Exception as exc:
        return False, f"registry unreadable: {exc}"


def default_reports(endpoint: str = "http://127.0.0.1:11434/api/tags",
                    tts_command: str | None = None) -> list[dict]:
    tts_cmd = tts_command or ""
    tts_cli = next((_which(c) for c in ("piper", "espeak-ng", "espeak", "festival") if _which(c)), None)
    remotion = _which("npm") is not None and _which("npx") is not None
    registry_ok, registry_detail = _registry_report()
    reports = [
        {"name": "python", "required": True, "present": _which("python") is not None, "detail": _which("python") or "missing"},
        {"name": "ffmpeg", "required": True, "present": _which("ffmpeg") is not None, "detail": "audio assembly and delivery"},
        {"name": "ffprobe", "required": True, "present": _which("ffprobe") is not None, "detail": "timing and delivery QA"},
        {"name": "node", "required": True, "present": _which("node") is not None, "detail": _which("node") or "missing"},
        {"name": "remotion", "required": True, "present": remotion, "detail": "npm/npx + Remotion renderer"},
        {"name": "ollama", "required": False, "present": _reachable(endpoint), "detail": f"grounding LLM at {endpoint}"},
        {"name": "tts", "required": False, "present": bool(tts_cmd) or tts_cli is not None, "detail": f"command={'present' if tts_cmd else 'missing'}, cli={tts_cli or 'none'}"},
        {"name": "faster-whisper", "required": False, "present": _module_available("faster_whisper"), "detail": "local word-timed captions"},
        {"name": "research-helpers", "required": False, "present": _module_available("ddgs") and _module_available("trafilatura"), "detail": "no-key source discovery"},
        {"name": "assets", "required": False, "present": registry_ok, "detail": registry_detail},
    ]
    return reports


def summarize(reports: list[dict]) -> dict:
    required = [r for r in reports if r.get("required")]
    missing = [r for r in required if not r.get("present")]
    return {
        "ok": not missing,
        "required": len(required),
        "missing": len(missing),
        "present": len(required) - len(missing),
        "missing_names": [r["name"] for r in missing],
    }


def render_text(reports: list[dict]) -> str:
    lines = ["FLVYT local production preflight", ""]
    for report in reports:
        marker = "[ok]" if report["present"] else "[  ]"
        need = "required" if report["required"] else "optional"
        lines.append(f" {marker} {report['name']:16} ({need:8}) {report['detail']}")
    summary = summarize(reports)
    lines.append("")
    lines.append(f"{summary['present']}/{summary['required']} required tools present")
    if not summary["ok"]:
        lines.append("Missing required tools: " + ", ".join(summary["missing_names"]))
    return "\n".join(lines)