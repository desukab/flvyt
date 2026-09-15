from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import env


def host_report(name: str, required: bool, present: bool) -> dict:
    state = "configured" if present else ("missing" if required else "optional")
    return {
        "name": name,
        "required": required,
        "present": present,
        "status": state,
        "stage": env.STAGE.get(name, "unknown"),
        "guidance": env.GUIDANCE.get(name),
        "detail": "detail",
    }


class DoctorTests(unittest.TestCase):
    def test_all_required_present(self):
        base = [
            {"name": "python", "required": True, "present": True, "detail": "x"},
            {"name": "ffmpeg", "required": True, "present": True, "detail": "x"},
            {"name": "node", "required": True, "present": True, "detail": "x"},
            {"name": "remotion", "required": True, "present": True, "detail": "x"},
            {"name": "ollama", "required": False, "present": True, "detail": "x"},
        ]
        summary = env.summarize(base)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["missing"], 0)

    def test_missing_required_reported(self):
        base = [
            {"name": "python", "required": True, "present": True, "detail": "x"},
            {"name": "ffmpeg", "required": True, "present": False, "detail": "x"},
            {"name": "node", "required": True, "present": True, "detail": "x"},
            {"name": "remotion", "required": True, "present": True, "detail": "x"},
        ]
        summary = env.summarize(base)
        self.assertFalse(summary["ok"])
        self.assertIn("ffmpeg", summary["missing_names"])

    def test_default_reports_uses_local_tools(self):
        with mock.patch.object(env, "_which") as w, \
             mock.patch.object(env, "_reachable") as r, \
             mock.patch.object(env, "_module_available") as m, \
             mock.patch.object(env, "_registry_report") as reg:
            w.side_effect = lambda name: f"/usr/bin/{name}"
            r.return_value = True
            m.return_value = True
            reg.return_value = (True, "registry")
            reports = env.default_reports("http://llm/api/tags")
            by_name = {rep["name"]: rep for rep in reports}
            self.assertTrue(by_name["ffmpeg"]["present"])
            self.assertTrue(by_name["ollama"]["present"])
            self.assertTrue(by_name["faster-whisper"]["present"])
            self.assertTrue(by_name["assets"]["present"])
            detail = env.render_text(reports)
            self.assertIn("required", detail)

    def test_tts_detects_cli_binary(self):
        with mock.patch.object(env, "_which") as w:
            w.side_effect = lambda name: "/usr/bin/piper" if name == "piper" else None
            reports = env.default_reports(tts_command=None)
            tts = next(r for r in reports if r["name"] == "tts")
            self.assertTrue(tts["present"])

    def test_doctor_status_matrix(self):
        base = [
            host_report("python", required=True, present=True),
            host_report("ffmpeg", required=True, present=False),
            host_report("ollama", required=False, present=True),
            host_report("tts", required=False, present=False),
        ]
        view = env.doctor(base)
        self.assertEqual(view["status"]["python"], "CONFIGURED")
        self.assertEqual(view["status"]["ffmpeg"], "MISSING")
        self.assertEqual(view["status"]["ollama"], "CONFIGURED")
        self.assertEqual(view["status"]["tts"], "OPTIONAL")
        self.assertFalse(view["ok"])
        self.assertEqual(view["missing_names"], ["ffmpeg"])

    def test_doctor_stage_mapping_and_guidance(self):
        base = [
            host_report("ffmpeg", required=True, present=False),
            host_report("tts", required=False, present=False),
        ]
        view = env.doctor(base)
        stages = {entry["stage"] for entry in view["stages"]}
        self.assertIn("audio assembly + mux", stages)
        self.assertIn("narration synthesis", stages)
        by_name = {r["name"]: r for r in base}
        self.assertTrue(by_name["ffmpeg"]["guidance"])
        self.assertIsNone(by_name["tts"]["guidance"])

    def test_render_text_contains_status_and_fix(self):
        base = [host_report("ffmpeg", required=True, present=False)]
        text = env.render_text(base)
        self.assertIn("MISSING", text)
        self.assertIn("fix:", text)
        self.assertIn("audio assembly + mux", text)


if __name__ == "__main__":
    unittest.main()