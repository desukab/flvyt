from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TtsTests(unittest.TestCase):
    def test_synthesize_runs_template_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            def fake_run(argv, input, text, check=True):
                out = Path(argv[argv.index("--output") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"\x00" * 16)
                self.assertEqual(argv[0], "fake-tts")
                self.assertIn("--model", argv)
                self.assertTrue(input)

            from engine.tts import synthesize, synthesize_beats
            with mock.patch("subprocess.run", side_effect=fake_run):
                audio = td / "voice.wav"
                synthesize("hello world", audio, "fake-tts --model {model} --output {output}", model="voicemodel")
                self.assertTrue(audio.exists())
                beats = [{"id": "b1", "text": "hello", "narration": None}]
                synthesize_beats(beats, td / "nar", "fake-tts --model {model} --output {output}", "voicemodel")
            manifest = json.loads((td / "nar/tts_manifest.json").read_text())
            self.assertIn("b1", manifest)

    def test_synthesize_empty_output_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("subprocess.run", return_value=None):
                from engine.tts import synthesize
                with self.assertRaises(RuntimeError):
                    synthesize("x", Path(td) / "none.wav", "true")

    def test_synthesize_empty_command_raises(self):
        from engine.tts import synthesize
        with self.assertRaises(ValueError):
            synthesize("x", "/tmp/x.wav", "  ")


class RetimeTests(unittest.TestCase):
    def test_retime_sets_seconds_and_pad(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            project = {
                "title": "t", "subtitle": "", "fps": 30,
                "beats": [
                    {"id": "b1", "kind": "evidence", "text": "x", "seconds": 3.0, "emphasis": "normal"},
                    {"id": "b2", "kind": "claim", "text": "y", "seconds": 3.0, "emphasis": "high"},
                ],
            }
            pf = td / "p.json"
            pf.write_text(json.dumps(project), encoding="utf-8")
            audio = td / "b1.wav"
            audio.write_bytes(b"\x00" * 10)
            audio2 = td / "b2.wav"
            audio2.write_bytes(b"\x00" * 10)
            manifest = {"b1": str(audio), "b2": str(audio2)}
            mf = td / "m.json"
            mf.write_text(json.dumps(manifest), encoding="utf-8")

            from engine.timing import retime_project
            with mock.patch("engine.timing.media_duration", return_value=2.0):
                changed = retime_project(pf, mf)
            self.assertEqual(changed, {"b1": 2.18, "b2": 2.38})
            data = json.loads(pf.read_text())
            self.assertEqual(data["beats"][0]["seconds"], 2.18)
            self.assertEqual(data["beats"][0]["pad_after"], 0.18)
            self.assertEqual(data["beats"][1]["pad_after"], 0.38)

    def test_retime_ignores_missing_manifest_entries(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            pf = td / "p.json"
            pf.write_text(json.dumps({"beats": [{"id": "b1", "seconds": 3.0}]}), encoding="utf-8")
            mf = td / "m.json"
            mf.write_text(json.dumps({}), encoding="utf-8")
            from engine.timing import retime_project
            changed = retime_project(pf, mf)
            self.assertEqual(changed, {})


class LocalLlmTests(unittest.TestCase):
    def test_generate_json_parses_response(self):
        body = json.dumps({"response": json.dumps({"claim": "x"})}).encode()
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = body
            from engine.local_llm import generate_json
            out = generate_json("prompt", model="m", endpoint="http://e")
            self.assertEqual(out["claim"], "x")


class QualityTests(unittest.TestCase):
    def test_probe_missing_file_fails(self):
        from engine.quality import probe
        report = probe(Path(__file__).parent / "nope.mp4")
        self.assertFalse(report["ok"])
        self.assertTrue(any("missing" in f for f in report.get("fails", [])))

    def test_probe_ffprobe_failure_returns_fails(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "boom"
            with tempfile.TemporaryDirectory() as td:
                target = Path(td) / "x.mp4"
                target.write_bytes(b"\x00" * 4)
                from engine.quality import probe
                report = probe(target)
            self.assertFalse(report["ok"])

    def test_probe_full_report(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "ok.mp4"
            target.write_bytes(b"\x00" * 16)
            streams = {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
                    {"codec_type": "audio", "sample_rate": 48000, "channels": 2},
                ],
                "format": {"duration": "12.5", "format_name": "mp4"},
            }

            class R:
                returncode = 0
                stdout = json.dumps(streams)

            with mock.patch("subprocess.run", return_value=R()):
                from engine.quality import probe
                report = probe(target)
            self.assertTrue(report["ok"])
            self.assertEqual(report["duration"], "12.5")


class AssetsTests(unittest.TestCase):
    def test_registry_validate_detects_issues(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            data = {
                "assets": [
                    {"id": "a1", "path": str(td / "missing.png"), "kind": "image", "license": "cc0"},
                    {"id": "a2", "path": str(td / "photo.png"), "kind": "image",
                     "tags": ["photo"], "license": "unsupported"},
                ],
            }
            f = td / "registry.json"
            f.write_text(json.dumps(data), encoding="utf-8")
            from engine.assets import AssetRegistry
            registry = AssetRegistry.load(f)
            errors = registry.validate(td)
            self.assertTrue(any("missing file" in e for e in errors))
            self.assertTrue(any("unsupported" in e for e in errors))

    def test_match_scores_tags(self):
        from engine.assets import Asset, AssetRegistry
        registry = AssetRegistry([
            Asset(id="chip", path="p.png", kind="image", tags=("semiconductor", "fab")),
            Asset(id="lab", path="q.png", kind="image", tags=("laboratory",)),
        ])
        matches = registry.match("semiconductor fab equipment", "image")
        self.assertEqual(matches[0].id, "chip")


class EditPolicyTests(unittest.TestCase):
    def test_high_emphasis_sets_punch(self):
        from engine.edit_policy import decision
        d = decision("evidence", "high")
        self.assertEqual(d.mode, "punch")
        base = decision("evidence")
        self.assertLess(d.min_seconds, base.min_seconds + 1e-9)

    def test_clamp_text_truncates(self):
        from engine.edit_policy import clamp_text, decision
        out = clamp_text("word " * 50, "evidence")
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), decision("evidence").max_text_chars + 1)


class ResearchTests(unittest.TestCase):
    def test_collect_requires_research_helpers(self):
        from engine.research import collect
        with self.assertRaises(RuntimeError):
            collect("topic", "/tmp/never.json")

    def test_collect_builds_sources(self):
        import types

        ddgs = types.ModuleType("ddgs")
        class DDGS:
            def text(self, topic, region, safesearch, max_results):
                return [{"title": "A", "href": "https://a.test/x", "body": "snip"}]
        ddgs.DDGS = DDGS

        trafilatura = types.ModuleType("trafilatura")
        trafilatura.fetch_url = lambda url: "<html>x</html>"
        trafilatura.extract = lambda html, include_comments=False: "extracted text"

        with mock.patch.dict("sys.modules", {"ddgs": ddgs, "trafilatura": trafilatura}):
            with tempfile.TemporaryDirectory() as td:
                from engine.research import collect
                out = Path(td) / "research.json"
                collect("topic", out, max_results=5)
                data = json.loads(out.read_text())
                self.assertEqual(data["sources"][0]["url"], "https://a.test/x")
                self.assertEqual(data["sources"][0]["text"], "extracted text")

    def test_collect_filters_duplicate_urls(self):
        import types
        ddgs = types.ModuleType("ddgs")
        class DDGS:
            def text(self, topic, region, safesearch, max_results):
                return [
                    {"title": "A", "href": "https://a.test/x", "body": "s1"},
                    {"title": "B", "href": "https://a.test/x", "body": "s2"},
                    {"title": "C", "href": "https://c.test/y", "body": "s3"},
                ]
        ddgs.DDGS = DDGS
        trafilatura = types.ModuleType("trafilatura")
        trafilatura.fetch_url = lambda url: None
        with mock.patch.dict("sys.modules", {"ddgs": ddgs, "trafilatura": trafilatura}):
            with tempfile.TemporaryDirectory() as td:
                from engine.research import collect
                data = json.loads(collect("topic", Path(td) / "r.json", max_results=5).read_text())
                self.assertEqual(len(data["sources"]), 2)
                self.assertEqual(data["sources"][0]["url"], "https://a.test/x")
                self.assertEqual(data["sources"][1]["url"], "https://c.test/y")


class TranscribeTests(unittest.TestCase):
    def test_requires_faster_whisper(self):
        from engine.transcribe import transcribe
        with self.assertRaises(RuntimeError):
            transcribe("/tmp/a.wav")


if __name__ == "__main__":
    unittest.main()