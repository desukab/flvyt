"""Tiny dependency-free adapter for a local Ollama-compatible LLM."""
from __future__ import annotations

import json
import urllib.request
from typing import Any


def generate_json(prompt: str, model: str = "llama3.2", endpoint: str = "http://127.0.0.1:11434/api/generate") -> Any:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}).encode()
    request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return json.loads(body["response"])
