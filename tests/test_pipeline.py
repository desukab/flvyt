from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import pipeline


def _evidence() -> dict:
    return {
        "title": "Test Topic",
        "thesis": "Fabrication nodes drive advanced semiconductor economics.",
        "evidence": [
            {
                "id": "e01",
                "claim": "Leading nodes are increasingly expensive to bring up.",
                "source": "https://example.test/report",
                "source_type": "article",
                "importance": "high",
                "tags": ["semiconductor", "economics"],
                "quote": "Costs scale with node complexity.",
            }
        ],
    }


def _project(tmp: str) -> Path:
    project = Path(tmp) / "p.json"
    project.write_text(json.dumps(_evidence()), encoding="utf-8")
    from engine.story import StoryPack, save_project
    save_project(StoryPack.load(project), str(project))
    return project


def _resume_state(tmp: str) -> Path:
    return Path(tmp) / "pipeline_state.json"


class KindTests(unittest.TestCase):
    def test_kind_detection(self):
        self.assertEqual(pipeline._kind({"beats": []}), "project")
        self.assertEqual(pipeline._kind({"evidence": []}), "evidence")
        self.assertEqual(pipeline._kind({"sources": []}), "research")

    def test_kind_rejects_unknown(self):
        with self.assertRaises(ValueError):
            pipeline._kind({})


class ProduceTests(unittest.TestCase):
    def test_produce_runs_render_from_ready_project(self):
        with tempfile.TemporaryDirectory() as td:
            project = _project(td)
            seen: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                seen.append(cmd)

            with mock.patch.object(pipeline, "_run", side_effect=fake_run):
                result = pipeline.produce(str(project), state_file=_resume_state(td))
            self.assertIn("editorial", [s["step"] for s in result["steps"]])
            self.assertIn("render", [s["step"] for s in result["steps"]])
            self.assertTrue(result["qa"]["ok"])
            self.assertTrue(seen, "expected staged subprocess call recorded")
            self.assertIn("scripts/render.py", seen[-1])

    def test_second_run_skips_unchanged_stages(self):
        with tempfile.TemporaryDirectory() as td:
            project = _project(td)
            out = Path(td) / "final.mp4"

            def fake_run(cmd, **kwargs):
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(b"x" * 64)
                Path(td, "qa.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

            state = _resume_state(td)
            with mock.patch.object(pipeline, "_run", side_effect=fake_run):
                first = pipeline.produce(str(project), out=str(out), state_file=state)
                second = pipeline.produce(str(project), out=str(out), state_file=state)
            self.assertTrue(first["qa"]["ok"])
            self.assertEqual(second["steps"][-1]["step"], "render")
            self.assertTrue(second["steps"][-1].get("skipped"))
            self.assertEqual(len(second["steps"]), len(first["steps"]))

    def test_force_bypasses_skip(self):
        with tempfile.TemporaryDirectory() as td:
            project = _project(td)
            out = Path(td) / "final.mp4"

            def fake_run(cmd, **kwargs):
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(b"x" * 64)

            state = _resume_state(td)
            with mock.patch.object(pipeline, "_run", side_effect=fake_run):
                pipeline.produce(str(project), out=str(out), state_file=state)
                forced = pipeline.produce(str(project), out=str(out),
                                          state_file=state, force=True)
            self.assertFalse(any(s.get("skipped") for s in forced["steps"]))

    def test_changed_input_reruns_stage(self):
        with tempfile.TemporaryDirectory() as td:
            project = _project(td)
            out = Path(td) / "final.mp4"
            out.write_bytes(b"x" * 64)

            def fake_run(cmd, **kwargs):
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(b"y" * 64)

            state = _resume_state(td)
            with mock.patch.object(pipeline, "_run", side_effect=fake_run):
                pipeline.produce(str(project), out=str(out), state_file=state)
                second = pipeline.produce(str(project), out=str(out), state_file=state)
                revised = json.loads(project.read_text(encoding="utf-8"))
                revised["beats"][0]["text"] = "REVISED HERO TEXT FOR THE RENDER."
                project.write_text(json.dumps(revised), encoding="utf-8")
                third = pipeline.produce(str(project), out=str(out), state_file=state)
            self.assertTrue(second["steps"][-1].get("skipped"))
            self.assertFalse(third["steps"][-1].get("skipped"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "requires local ffmpeg/ffprobe")
    def test_narration_synthesized_before_retime_and_master_matches_picture(self):
        """A single build must retime the plan with audio durations and size the
        narration master exactly to the picture (intro + beats), so the delivery
        gates see no silent tail and no re-floored dense shots."""
        from engine.audio import duration

        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            project = _project(home)
            project = home / "p.json"
            project.write_text(json.dumps(json.loads(project.read_text(encoding="utf-8"))),
                               encoding="utf-8")
            out = home / "final.mp4"

            def fake_run(cmd, **kwargs):
                args = [str(a) for a in cmd]
                if any("synthesize.py" in a for a in args):
                    out_dir = args[args.index("--out-dir") + 1]
                    base = Path(pipeline.ROOT) / out_dir
                    base.mkdir(parents=True, exist_ok=True)
                    beats = json.loads(project.read_text(encoding="utf-8"))["beats"]
                    manifest: dict[str, str] = {}
                    for beat in beats:
                        wav = base / f"{beat['id']}.wav"
                        subprocess.run([
                            "ffmpeg", "-v", "error", "-y",
                            "-f", "lavfi", "-i", "sine=frequency=220:duration=0.3",
                            "-ar", "48000", "-ac", "1", str(wav),
                        ], check=True)
                        manifest[beat["id"]] = str(wav)
                    (base / "tts_manifest.json").write_text(
                        json.dumps(manifest, indent=2), encoding="utf-8")
                elif any("render.py" in a for a in args):
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(b"x" * 64)
                elif any("captions.py" in a for a in args) or any("transcribe.py" in a for a in args):
                    pass

            with mock.patch.object(pipeline, "ROOT", home), \
                 mock.patch.object(pipeline, "WORK", home / "out"), \
                 mock.patch.object(pipeline, "STATE_FILE", home / "out" / "pipeline_state.json"), \
                 mock.patch.object(pipeline, "_run", side_effect=fake_run):
                pipeline.produce(str(project), out=str(out), state_file=home / "state.json",
                                 tts_command="espeak-ng -w {output}", auto_captions=False)

            raw = json.loads(project.read_text(encoding="utf-8"))
            self.assertTrue(raw.get("timed_by_audio"),
                            "plan must be marked timed_by_audio after narration")
            master = home / "out" / "narration" / "master.wav"
            self.assertTrue(master.exists(), "narration master must exist")
            beats = raw["beats"]
            self.assertTrue(all(b["pad_after"] > 0 for b in beats),
                            "breath schedule must be recorded on every beat")

            from engine.project import INTRO_SECONDS, Project
            final = Project.load(project)
            expected_video = final.duration_frames() / final.fps
            self.assertAlmostEqual(duration(master), expected_video, delta=0.2,
                                   msg="audio master must equal the picture budget")


class FailureTests(unittest.TestCase):
    def test_stage_failure_reports_command(self):
        with tempfile.TemporaryDirectory() as td:
            project = _project(td)

            def boom(cmd, **kwargs):
                if any("render.py" in a for a in cmd):
                    raise pipeline.StageFailed("render", cmd, 23, "exploded output")

            with mock.patch.object(pipeline, "_run", side_effect=boom):
                with self.assertRaises(pipeline.StageFailed) as ctx:
                    pipeline.produce(str(project), state_file=_resume_state(td))
            self.assertEqual(ctx.exception.stage, "render")
            self.assertEqual(ctx.exception.returncode, 23)
            failure = ctx.exception.report["failure"]
            self.assertEqual(failure["step"], "render")
            self.assertIn("scripts/render.py", failure["command"])
            self.assertIn("exploded", failure["output"])
            self.assertIn("resume", failure["resume"])

    def test_run_captures_failing_subprocess_output(self):
        command = [sys.executable, "-c",
                   "import sys; print('oops-message', file=sys.stderr); sys.exit(7)"]
        with self.assertRaises(pipeline.StageFailed) as ctx:
            pipeline._run(command, stage="probe")
        self.assertEqual(ctx.exception.returncode, 7)
        self.assertIn("oops-message", ctx.exception.output)

    def test_run_raises_on_missing_executable(self):
        with self.assertRaises(pipeline.StageFailed):
            pipeline._run(["/nonexistent/flvyt-binary-xyz"], stage="render")


if __name__ == "__main__":
    unittest.main()