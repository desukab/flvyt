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


# Pipeline stage that consumes each tool, and concise install guidance for the
# required ones (Termux-friendly, since the repo targets on-device production).
STAGE = {
    "python": "pipeline runner",
    "ffmpeg": "audio assembly + mux",
    "ffprobe": "timing + delivery QA",
    "node": "Remotion runtime",
    "remotion": "frame render",
    "ollama": "evidence grounding",
    "tts": "narration synthesis",
    "faster-whisper": "word-timed captions",
    "research-helpers": "source discovery",
    "assets": "license-cleared media",
}

GUIDANCE = {
    "python": "install Python 3.12+ (Termux: pkg install python)",
    "ffmpeg": "install FFmpeg (Termux: pkg install ffmpeg)",
    "ffprobe": "install FFmpeg; it ships ffprobe (Termux: pkg install ffmpeg)",
    "node": "install Node 18+ (Termux: pkg install nodejs)",
    "remotion": "from the repo root run 'npm install' then 'npx remotion'",
}


def default_reports(endpoint: str = "http://127.0.0.1:11434/api/tags",
                    tts_command: str | None = None) -> list[dict]:
    tts_cmd = tts_command or ""
    tts_cli = next((_which(c) for c in ("piper", "espeak-ng", "espeak", "festival") if _which(c)), None)
    remotion = _which("npm") is not None and _which("npx") is not None
    registry_ok, registry_detail = _registry_report()
    specs = [
        {"name": "python", "required": True, "present": _which("python") is not None, "detail": _which("python") or "missing"},
        {"name": "ffmpeg", "required": True, "present": _which("ffmpeg") is not None, "detail": "audio assembly and delivery"},
        {"name": "ffprobe", "required": True, "present": _which("ffprobe") is not None, "detail": "timing and delivery QA"},
        {"name": "node", "required": True, "present": _which("node") is not None, "detail": _which("node") or "missing"},
        {"name": "remotion", "required": True, "present": remotion, "detail": "npm/npx + Remotion renderer"},
        {"name": "ollama", "required": False, "present": _reachable(endpoint), "detail": f"optional enhancement; deterministic verbatim-source fallback covers grounding ({endpoint})"},
        {"name": "tts", "required": False, "present": bool(tts_cmd) or tts_cli is not None, "detail": f"command={'present' if tts_cmd else 'missing'}, cli={tts_cli or 'none'}"},
        {"name": "faster-whisper", "required": False, "present": _module_available("faster_whisper"), "detail": "local word-timed captions"},
        {"name": "research-helpers", "required": False, "present": _module_available("ddgs") and _module_available("trafilatura"), "detail": "no-key source discovery"},
        {"name": "assets", "required": False, "present": registry_ok, "detail": registry_detail},
    ]
    reports = []
    for spec in specs:
        present = spec["present"]
        status = ("configured" if present else
                  ("missing" if spec["required"] else "optional"))
        reports.append({
            "name": spec["name"],
            "required": spec["required"],
            "present": present,
            "status": status,
            "stage": STAGE.get(spec["name"], "unknown"),
            "guidance": GUIDANCE.get(spec["name"]),
            "detail": spec["detail"],
        })
    return reports


STATUS_LABEL = {"configured": "CONFIGURED", "missing": "MISSING", "optional": "OPTIONAL"}


def doctor(reports: list[dict]) -> dict:
    """Per-stage view of the preflight: statuses + guidance, grouped by stage."""
    reports = list(reports)
    required = [r for r in reports if r.get("required")]
    missing = [r for r in required if not r.get("present")]
    staged: list[dict] = []
    for stage in sorted({r.get("stage", "") for r in reports}):
        staged.append({"stage": stage, "tools": sorted(
            [r["name"] for r in reports if r.get("stage") == stage])})
    return {
        "ok": not missing,
        "required": len(required),
        "present": len(required) - len(missing),
        "missing": len(missing),
        "missing_names": [r["name"] for r in missing],
        "stages": staged,
        "status": {r["name"]: STATUS_LABEL.get(r["status"], r["status"]) for r in reports},
    }


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
    for report in sorted(reports, key=lambda r: (not r["required"], r["name"])):
        marker = "[ok]" if report["present"] else "[  ]"
        need = "required" if report["required"] else "optional"
        status = STATUS_LABEL.get(report["status"], report["status"])
        lines.append(f" {marker} {report['name']:16} ({status:10} {need:8}) "
                     f"stage: {report['stage']}")
        lines.append(f"        {report['detail']}")
        if report["required"] and not report["present"] and report.get("guidance"):
            lines.append(f"        fix: {report['guidance']}")
    lines.append("")
    summary = doctor(reports)
    lines.append(f"{summary['present']}/{summary['required']} required tools present")
    if not summary["ok"]:
        lines.append("Missing required tools: " + ", ".join(summary["missing_names"]))
        lines.append("Fix the required tools above, then re-run 'flvyt doctor'.")
    else:
        lines.append("Required pipeline is ready. Optional extras can be added per stage.")
    return "\n".join(lines)