"""Frame-level delivery QA guards (signalstats)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.quality import probe_frames


def _ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def _clip(path: Path, source: str) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", source,
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True)


@unittest.skipUnless(_ffmpeg_ok(), "ffmpeg not available")
class FrameQualityTests(unittest.TestCase):
    def test_all_black_render_is_failed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "black.mp4"
            _clip(p, "color=c=black:size=1280x720:rate=30:d=4")
            report = probe_frames(p)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("no visible signal" in f for f in report["fails"]),
                report["fails"])

    def test_bright_render_passes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.mp4"
            _clip(p, "testsrc=size=1280x720:rate=30:d=4")
            report = probe_frames(p)
            self.assertTrue(report["ok"], report["fails"])
            self.assertGreater(report["luma_max_p5"], 100)


if __name__ == "__main__":
    unittest.main()