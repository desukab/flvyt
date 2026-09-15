from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import audio, editorial_quality, manifest
from engine.timing import retime_project


def _evidence() -> dict:
    thesis = ("A local production fits the entire documentary pipeline "
              "onto a single on-device installation.")
    return {
        "title": "Local Production",
        "thesis": thesis,
        "evidence": [
            {
                "id": f"e{i:02d}",
                "claim": claim,
                "source": "https://example.test/local",
                "source_type": "article",
                "importance": "high",
                "tags": ["local"],
                "quote": claim,
            }
            for i, claim in enumerate([
                "Transistors shrink, and cost per wafer keeps climbing.",
                "EUV lithography prints patterns smaller than visible light.",
                "At the leading edge every extra nanometre costs a fortune.",
                "Fabs pool billions of dollars into a single cleanroom.",
                "Yield engineering turns slow chips into viable products.",
            ])
        ],
    }


class LocalEspeakTests(unittest.TestCase):
    def _tts(self) -> str | None:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not binary:
            return None
        return f"{binary} -s 150 -w {{output}}"

    def _pipeline_prereqs_present(self) -> bool:
        return all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe"))

    def test_local_espeak_synthesize_assemble_qa_manifest(self):
        command = self._tts()
        if not self._pipeline_prereqs_present():
            self.skipTest("ffmpeg/ffprobe unavailable")
        if not command:
            self.skipTest("no local espeak-ng/espeak binary")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "p.json"
            project.write_text(json.dumps(_evidence()), encoding="utf-8")

            from engine.story import StoryPack, save_project
            save_project(StoryPack.load(project), str(project))
            beats = json.loads(project.read_text(encoding="utf-8"))["beats"]

            out_dir = root / "narration"
            from engine.tts import synthesize_beats
            synthesized = synthesize_beats(beats, out_dir, command)
            manifest_path = out_dir / "tts_manifest.json"
            self.assertTrue(manifest_path.exists())
            self.assertGreaterEqual(len(synthesized), 3)
            for beat_id, wav in synthesized.items():
                self.assertGreater(Path(wav).stat().st_size, 0,
                                   f"no audio produced for {beat_id}")

            retime_project(project, manifest_path)
            from engine.pipeline import refresh_editorial_plan
            refresh_editorial_plan(project)
            beats_data = json.loads(project.read_text(encoding="utf-8"))["beats"]
            master = audio.assemble_narration(beats_data, synthesized,
                                              out_dir / "master.wav", cwd=root)
            self.assertGreater(audio.duration(master), 1.0,
                               "narration master unexpectedly silent/absent")

            qa = editorial_quality.report_to_path(
                project, root / "editorial_qa.json")
            self.assertIn("ok", qa)
            write_manifest = manifest.write_manifest(
                project, root / "manifest.json", {"ok": True}, qa,
                narration={"master": str(master)},
                render={"fps": 30, "width": 1920, "height": 1080})
            written = json.loads(write_manifest.read_text(encoding="utf-8"))
            self.assertIn("master", written["narration"])
            self.assertIn("ffprobe", written["software"])
            self.assertEqual(written["qa"]["frame"], {})


if __name__ == "__main__":
    unittest.main()