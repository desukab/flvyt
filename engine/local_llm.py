"""Adapter for an Ollama-compatible local LLM (optional enhancement)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from engine.grounding import GroundingUnavailable


def generate_json(prompt: str, model: str = "llama3.2",
                  endpoint: str = "http://127.0.0.1:11434/api/generate",
                  *, options: dict[str, Any] | None = None,
                  timeout: int = 300) -> Any:
    """POST a prompt with a JSON-output guarantee and a strict generation budget.

    `options` maps to Ollama's generation parameters. Grounding passes
    temperature=0 plus a num_predict cap so a CPU-only model cannot run past the
    HTTP timeout the way an unbounded structured-output request does.
    """
    payload = {"model": model, "prompt": prompt, "stream": False,
               "format": "json", "options": dict(options or {})}
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise GroundingUnavailable(f"{endpoint}: {exc}") from exc
    return json.loads(body["response"])