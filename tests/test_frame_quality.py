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
from engine.quality import probe_delivery, probe_frames, scene_cuts, silence_tail


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


def _tone_clip(path: Path, *, color_a: str = "testsrc",
               seconds: int = 6, tone: float = 5.0) -> None:
    """Steady picture with continuous 440 Hz tone for `tones` seconds."""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color_a}:size=1280x720:rate=30:d={seconds}",
        "-f", "lavfi", "-i", f"aevalsrc=s=48000:d={tone}:exprs='0.5*sin(2*PI*440*t)|0.5*sin(2*PI*440*t)'",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True)


def _cutting_clip(path: Path, *, seconds_each: float = 1.5,
                  tone: float = 6.0) -> None:
    """Alternating black/white blocks over continuous tone: an active edit."""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=black:size=1280x720:rate=30:d={seconds_each}",
        "-f", "lavfi", "-i", f"color=c=white:size=1280x720:rate=30:d={seconds_each}",
        "-f", "lavfi", "-i", f"color=c=black:size=1280x720:rate=30:d={seconds_each}",
        "-f", "lavfi", "-i", f"color=c=white:size=1280x720:rate=30:d={seconds_each}",
        "-f", "lavfi", "-i", f"aevalsrc=s=48000:d={tone}:exprs='0.5*sin(2*PI*440*t)|0.5*sin(2*PI*440*t)'",
        "-filter_complex", "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
        "-map", "[v]", "-map", "4:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True)


def _tail_clip(path: Path, *, speech: float = 2.5, silence: float = 2.5) -> None:
    """Picture total runs through `speech` + `silence`, then dead air."""
    total = speech + silence
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=gray:size=1280x720:rate=30:d={total}",
        "-f", "lavfi", "-i", f"aevalsrc=s=48000:d={speech}:exprs='0.5*sin(2*PI*440*t)|0.5*sin(2*PI*440*t)'",
        "-f", "lavfi", "-i", f"aevalsrc=s=48000:d={silence}:exprs='0|0'",
        "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[a]",
        "-map", "0:v", "-map", "[a]",
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

    def test_active_edit_passes_cut_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cuts.mp4"
            _cutting_clip(p)
            report = scene_cuts(p)
            self.assertTrue(report["ok"], report["fails"])
            self.assertGreaterEqual(report["cuts"], 2)
            self.assertLessEqual(report["cut_max_gap"], 3.0)

    def test_still_slideshow_fails_cut_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "still.mp4"
            _tone_clip(p, color_a="gray", seconds=12, tone=12.0)
            report = scene_cuts(p)
            self.assertFalse(report["ok"])
            self.assertTrue(any("never cuts" in f for f in report["fails"]))

    def test_continuous_audio_passes_tail_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tone.mp4"
            _tone_clip(p, color_a="gray")
            report = silence_tail(p)
            self.assertTrue(report["ok"], report["fails"])
            self.assertLess(report["tail"], 1.5)

    def test_dead_air_at_end_fails_tail_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tail.mp4"
            _tail_clip(p, speech=2.5, silence=2.5)
            report = silence_tail(p)
            self.assertFalse(report["ok"])
            self.assertGreater(report["tail"], 1.9)
            self.assertLess(report["tail"], 3.1)

    def test_probe_delivery_full_surface(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "good.mp4"
            _cutting_clip(p)
            report = probe_delivery(p, expect_narration=True)
            self.assertTrue(report["ok"], report["fails"])
            for key in ("duration", "cuts", "cut_median", "tail"):
                self.assertIn(key, report)


if __name__ == "__main__":
    unittest.main()