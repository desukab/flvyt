from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _research(sources: list[dict] | None = None, topic: str = "Renewable grid storage") -> dict:
    defaults = [
        {
            "title": "Battery Packs Stack Up",
            "url": "https://energy.test/batteries",
            "snippet": "Grid batteries are scaling quickly.",
            "text": (
                "Utility-scale battery capacity doubled last year. "
                "Lithium-ion cells dominate the newest deployments. "
                "Engineers pair storage with solar farms to smooth evening demand."
            ),
        },
        {
            "title": "Pumped Hydro Keeps Working",
            "url": "https://hydro.test/pumped",
            "snippet": "Pumped hydro remains the oldest grid storage method.",
            "text": (
                "Pumped hydro stations move water between reservoirs to store power. "
                "They supply about ninety percent of installed storage capacity today."
            ),
        },
    ]
    return {"topic": topic, "sources": [dict(s, **{"text": s.get("text", ""), "snippet": s.get("snippet", "")}) for s in (sources or defaults)]}


class GroundingExtractTests(unittest.TestCase):
    def setUp(self) -> None:
        from engine import grounding
        self.extract = grounding.extract

    def test_claims_are_verbatim_source_sentences(self):
        pack = self.extract(_research(topic="Renewable grid storage"))
        self.assertEqual(pack["title"], "Renewable grid storage")
        self.assertEqual(pack["grounding"]["method"], "deterministic-source-extraction")
        self.assertIn("verbatim", pack["grounding"]["note"])
        for item in pack["evidence"]:
            source = next(s for s in _research()["sources"] if s["url"] == item["source"])
            self.assertIn(item["claim"], source["text"])
            self.assertEqual(item["quote"], item["claim"])
            self.assertIn(item["source"], {s["url"] for s in _research()["sources"]})

    def test_never_invents_any_claim(self):
        pack = self.extract(_research(topic="Quantum networking"))
        materials = {s["url"]: s["text"] + " " + s["snippet"] for s in _research()["sources"]}
        for item in pack["evidence"]:
            self.assertIn(item["claim"].rstrip("."), materials[item["source"]])
        self.assertTrue(pack["evidence"])

    def test_sources_without_text_are_skipped_not_claimed(self):
        research = _research(topic="Tin whiskers")
        research["sources"].append({
            "title": "Unreachable Page",
            "url": "https://down.test/page",
            "snippet": "",
            "text": "",
        })
        pack = self.extract(research)
        self.assertNotIn("https://down.test/page", [e["source"] for e in pack["evidence"]])
        skipped = [s["url"] for s in pack["grounding"]["sources_skipped"]]
        self.assertIn("https://down.test/page", skipped)

    def test_snippet_fallback_keeps_source_when_text_missing(self):
        research = _research(topic="Thermal imaging")
        research["sources"].append({
            "title": "Snippet Only",
            "url": "https://snip.test/ir",
            "snippet": "Infrared cameras reveal heat leaking from buildings.",
            "text": "",
        })
        pack = self.extract(research)
        item = next(e for e in pack["evidence"] if e["source"] == "https://snip.test/ir")
        self.assertIn(item["claim"], "Infrared cameras reveal heat leaking from buildings.")

    def test_importance_deterministic_and_grounding_metadata(self):
        pack = self.extract(_research(topic="Edge computing"))
        self.assertEqual(pack["evidence"][0]["importance"], "high")
        self.assertTrue(all(e["importance"] in {"high", "normal"} for e in pack["evidence"]))
        self.assertEqual(pack["grounding"]["engine"], "engine.grounding.extract")
        self.assertEqual(set(pack["grounding"]["sources_used"]),
                         {s["url"] for s in _research()["sources"]})

    def test_repeated_sentences_are_deduplicated(self):
        research = _research(topic="Space debris")
        shared = "Objects in low orbit now number more than thirty thousand."
        research["sources"] = [
            {"title": "A", "url": "https://a.test/1", "snippet": "", "text": shared},
            {"title": "B", "url": "https://b.test/2", "snippet": shared, "text": shared + " Tracking stations catalog each one."},
        ]
        pack = self.extract(research)
        claims = [e["claim"] for e in pack["evidence"]]
        self.assertEqual(len(claims), len(set(claims)))


class GroundScriptTests(unittest.TestCase):
    def test_falls_back_when_llm_unavailable(self):
        from engine.grounding import GroundingUnavailable
        from scripts import ground
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            research = _research(topic="Printed photonics")
            out = td / "evidence.json"
            with mock.patch.object(ground, "generate_json",
                                   side_effect=GroundingUnavailable("endpoint down")):
                ground.ground(research, out, model="x", endpoint="http://127.0.0.1:9")
            pack = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(pack["grounding"]["method"], "deterministic-source-extraction")
            self.assertTrue(pack["evidence"])
            self.assertTrue(all(e["source"] in {s["url"] for s in research["sources"]} for e in pack["evidence"]))

    def test_require_llm_fails_when_unavailable(self):
        from engine.grounding import GroundingUnavailable, GroundingFailed
        from scripts import ground
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ground, "generate_json",
                                   side_effect=GroundingUnavailable("down")):
                with self.assertRaises(GroundingFailed):
                    ground.ground(_research(), Path(td) / "e.json",
                                  model="x", endpoint="http://127.0.0.1:9", require_llm=True)

    def test_llm_path_used_when_available(self):
        from scripts import ground
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            research = _research(topic="Optical interconnects")
            pack_out = td / "e.json"
            llm_evidence = [{
                "id": "e01", "claim": "The gap between switches is the real cost.",
                "source": "https://energy.test/batteries", "source_type": "article",
                "importance": "high", "tags": [], "quote": "The gap is the real cost.",
            }]
            with mock.patch.object(ground, "generate_json",
                                   return_value={"title": "T", "thesis": "t", "evidence": llm_evidence}):
                ground.ground(research, pack_out, model="m", endpoint="http://e")
            pack = json.loads(pack_out.read_text(encoding="utf-8"))
            self.assertEqual(pack["grounding"]["method"], "ollama")
            self.assertEqual(pack["grounding"]["model"], "m")
            self.assertEqual(len(pack["evidence"]), 1)


class BoundedContextTests(unittest.TestCase):
    """Regression: a ~79KB research pack must never be sent unbounded to the LLM."""

    def test_compact_sources_truncates_long_text(self):
        from engine.grounding import compact_sources
        research = _research()
        research["sources"].append({
            "title": "Big Page", "url": "https://big.test/1",
            "snippet": "snip", "text": "y" * 50000,
        })
        rows = compact_sources(research, max_text_chars=1200)
        big = next(r for r in rows if r["url"] == "https://big.test/1")
        self.assertEqual(len(big["text"]), 1200)

    def test_compact_sources_snippet_fallback(self):
        from engine.grounding import compact_sources
        research = _research()
        research["sources"][0]["text"] = ""
        research["sources"][0]["snippet"] = "S" * 3000
        rows = compact_sources(research, max_text_chars=100)
        self.assertEqual(rows[0]["text"], "S" * 100)

    def test_compact_sources_skips_urless_rows_and_caps(self):
        from engine.grounding import compact_sources
        research = _research()
        research["sources"].append({"title": "No URL", "snippet": "x", "text": "y"})
        rows = compact_sources(research, max_sources=2)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["url"] for r in rows))

    def test_merge_evidence_renumbers_and_dedupes(self):
        from engine.grounding import merge_evidence
        parts = [
            {"evidence": [
                {"claim": "First claim here.", "source": "https://a.test/1",
                 "source_type": "article", "importance": "high", "tags": ["x"], "quote": "q"},
                {"claim": "Repeated claim.", "source": "https://b.test/2",
                 "source_type": "paper", "importance": "bogus", "tags": [], "quote": "q"},
            ]},
            {"evidence": [
                {"claim": "Repeated claim.", "source": "https://b.test/2",
                 "source_type": "paper", "importance": "normal", "quote": "q"},
                {"claim": "Third claim.", "source": "https://c.test/3",
                 "source_type": "article", "importance": "high", "quote": "q"},
            ]},
        ]
        merged = merge_evidence(parts, max_evidence=12)
        self.assertEqual([e["id"] for e in merged], ["e01", "e02", "e03"])
        self.assertEqual(merged[1]["importance"], "normal")
        self.assertEqual(merged[0]["importance"], "high")
        self.assertEqual(len({e["claim"] for e in merged}), 3)

    def test_title_thesis_derived_deterministically(self):
        from engine.grounding import title_and_thesis
        research = _research(topic="Optical interconnects")
        evidence = [
            {"id": "e01", "claim": "plain claim", "importance": "normal"},
            {"id": "e02", "claim": "thesis claim", "importance": "high"},
        ]
        title, thesis = title_and_thesis(research, evidence)
        self.assertEqual(title, "Optical interconnects")
        self.assertEqual(thesis, "thesis claim")


class BoundedGroundingTests(unittest.TestCase):
    """The LLM grounding path must chunk sources and bound every prompt."""

    def _many_sources(self, count: int = 9) -> dict:
        research = _research(topic="The Hidden Infrastructure Behind GPS")
        for i in range(count):
            research["sources"].append({
                "title": f"Source {i}", "url": f"https://n.test/{i}",
                "snippet": f"snippet {i}",
                "text": f"Wire {i}. This sentence is long enough to support a claim "
                        f"about the topic and nothing more.{' x' * 200}",
            })
        return research

    def test_llm_path_is_chunked_and_bounded(self):
        from scripts import ground
        research = self._many_sources(9)
        captured: dict[str, list] = {"prompts": [], "options": []}

        def fake_generate(prompt, model, endpoint, options=None, timeout=300):
            captured["prompts"].append(prompt)
            captured["options"].append(options)
            chunk_urls = re.findall(r"uri: (\S+)", prompt)
            return {"evidence": [
                {"claim": f"Claim backed by {u}.", "source": u, "source_type": "article",
                 "importance": "normal", "tags": [], "quote": "q"} for u in chunk_urls
            ]}

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "e.json"
            with mock.patch.object(ground, "generate_json", side_effect=fake_generate):
                ground.ground(research, out, model="m", endpoint="http://e",
                              max_sources=12)
                pack = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(len(captured["prompts"]), 3)  # 9 sources / chunk_size 4
        all_urls = {s["url"] for s in research["sources"]}
        seen_urls = set()
        for prompt in captured["prompts"]:
            self.assertLess(len(prompt), 12000)  # never a 79KB prompt
            uris = set(re.findall(r"uri: (\S+)", prompt))
            self.assertTrue(uris <= all_urls)
            seen_urls |= uris
        self.assertEqual(seen_urls, all_urls)
        self.assertTrue(all(o == {"temperature": 0.0, "num_predict": 600} for o in captured["options"]))

        self.assertEqual(pack["grounding"]["method"], "ollama")
        self.assertEqual(pack["grounding"]["chunk_count"], 3)
        self.assertTrue(pack["evidence"])
        self.assertTrue(all(e["source"] in all_urls for e in pack["evidence"]))
        self.assertTrue(all(e["importance"] in {"high", "normal"} for e in pack["evidence"]))

    def test_large_single_source_stays_bounded(self):
        from scripts import ground
        research = _research()
        research["sources"][0]["text"] = "y" * 40000
        captured: dict[str, list] = {"prompts": []}

        def fake_generate(prompt, model, endpoint, options=None, timeout=300):
            captured["prompts"].append(prompt)
            return {"evidence": [{
                "claim": "Text excerpt.", "source": "https://energy.test/batteries",
                "source_type": "article", "importance": "normal",
                "tags": [], "quote": "excerpt",
            }]}

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "e.json"
            with mock.patch.object(ground, "generate_json", side_effect=fake_generate):
                ground.ground(research, out, model="m", endpoint="http://e")
            pack = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(captured["prompts"]), 1)
        self.assertLess(len(captured["prompts"][0]), 8000)
        self.assertNotIn("y" * 40000, captured["prompts"][0])
        self.assertEqual(pack["grounding"]["method"], "ollama")

    def test_empty_llm_evidence_raises_explicitly(self):
        from engine.grounding import GroundingFailed
        from scripts import ground
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ground, "generate_json",
                                   return_value={"evidence": []}):
                with self.assertRaises(GroundingFailed):
                    ground.ground(_research(), Path(td) / "e.json",
                                  model="m", endpoint="http://e")

    def test_unverified_llm_source_raises(self):
        from engine.grounding import GroundingFailed
        from scripts import ground
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ground, "generate_json",
                                   return_value={"evidence": [{
                                       "claim": "Made up.",
                                       "source": "https://unlisted.test/9",
                                       "quote": "made up",
                                   }]}):
                with self.assertRaises(GroundingFailed):
                    ground.ground(_research(), Path(td) / "e.json",
                                  model="m", endpoint="http://e")


class ProvenanceTests(unittest.TestCase):
    def test_attach_provenance_embeds_grounding_metadata(self):
        from engine.grounding import attach_provenance
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p.json"
            project.write_text(json.dumps({
                "title": "T", "subtitle": "s", "fps": 30, "beats": [{"id": "b1"}],
            }), encoding="utf-8")
            provenance = {"evidence_pack": "evidence.json",
                          "grounding": {"method": "deterministic-source-extraction"}}
            attach_provenance(project, provenance)
            data = json.loads(project.read_text(encoding="utf-8"))
            self.assertEqual(data["provenance"]["grounding"]["method"],
                             "deterministic-source-extraction")
            self.assertEqual(data["provenance"]["evidence_pack"], "evidence.json")


if __name__ == "__main__":
    unittest.main()