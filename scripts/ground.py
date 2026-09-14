#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.local_llm import generate_json

p = argparse.ArgumentParser(description="Turn collected research into a source-grounded evidence pack using a local LLM")
p.add_argument("research_json")
p.add_argument("--out", default="projects/evidence.generated.json")
p.add_argument("--model", default="llama3.2")
p.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
a = p.parse_args()

research = json.loads(Path(a.research_json).read_text(encoding="utf-8"))
source_text = json.dumps(research, ensure_ascii=False)
prompt = f"""
You are the research editor for a technology documentary. Produce ONLY a JSON object.
Every factual claim must be directly supported by one of the supplied sources.
Never invent numbers, dates, names, quotes, causality or conclusions.
Do not use a search snippet when extracted source text is available.
For each evidence item include the source URL and a short exact quote from the supplied source text that supports the claim.
Prefer primary sources, company filings, government material, academic papers and reputable reporting.
Mark importance high only when it is central to the thesis.
Return this schema:
{{"title":"...","thesis":"...","evidence":[{{"id":"e01","claim":"...","source":"https://...","source_type":"article|primary|paper|filing|interview|other","importance":"high|normal","tags":["..."] ,"quote":"..."}}]}}

RESEARCH:
{source_text}
"""
result = generate_json(prompt, model=a.model, endpoint=a.endpoint)
if not isinstance(result, dict) or "evidence" not in result:
    raise SystemExit("Local model returned an invalid evidence schema")

# Hard safety gate: every generated evidence item must point to a URL present in research.
known = {str(row.get("url")) for row in research.get("sources", [])}
for item in result.get("evidence", []):
    if str(item.get("source")) not in known:
        raise SystemExit(f"Grounding gate failed: unknown source {item.get('source')}")
    if not item.get("quote"):
        raise SystemExit(f"Grounding gate failed: missing supporting quote for {item.get('id')}")

out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(out)
