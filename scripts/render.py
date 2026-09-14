#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.audio import concat_wavs, mix
from engine.director import direct
from engine.project import Project
from engine.quality import probe
from engine.captions import words_to_srt


def _ffmpeg_audio(video: Path, audio: Path | None, out: Path) -> None:
    if audio is None:
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(video),
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-shortest", str(out),
        ], check=True)
        return
    # Pad/trim narration to the picture duration. This prevents a TTS speed
    # mismatch from silently shortening the documentary.
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
        "-filter_complex", "[1:a]apad,atrim=0:99999[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "256k", "-t", f"{probe_duration(video):.3f}", str(out),
    ], check=True)


def probe_duration(path: Path) -> float:
    r = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(r.stdout.strip() or 0)


def _mux_srt(video: Path, srt: Path, out: Path) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(srt),
        "-map", "0:v:0", "-map", "0:a:0?", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng", str(out),
    ], check=True)


def _find_narration(project_path: Path, root: Path) -> Path | None:
    candidates = [
        root / "out/narration/master.wav",
        root / "out/narration/narration.wav",
        project_path.parent / "narration.wav",
    ]
    manifest = root / "out/narration/tts_manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        ordered = [Path(data[b["id"]]) for b in Project.load(project_path).props()["beats"] if b["id"] in data]
        if ordered:
            return concat_wavs(ordered, root / "out/narration/master.wav")
    for path in candidates:
        if path.exists():
            return path
    return None


def _find_music(root: Path) -> Path | None:
    for path in (root / "assets/music.wav", root / "assets/music.mp3", root / "assets/music.m4a"):
        if path.exists():
            return path
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Render a FLVYT documentary project")
    p.add_argument("project", help="Path to project JSON")
    p.add_argument("--out", default="out/final.mp4")
    p.add_argument("--narration", help="Override narration WAV")
    p.add_argument("--music", help="Override music file")
    p.add_argument("--srt", help="Optional SRT subtitle file to mux")
    p.add_argument("--transcript", help="Whisper JSON; creates SRT automatically")
    args = p.parse_args()

    project_path = ROOT / args.project if not Path(args.project).is_absolute() else Path(args.project)
    project = direct(Project.load(project_path))
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="flvyt_") as td:
        work = Path(td)
        props = work / "props.json"
        rendered = work / "rendered.mp4"
        audio_mix = work / "mix.wav"
        with_audio = work / "with_audio.mp4"
        final = work / "final.mp4"
        props.write_text(json.dumps(project.props(), indent=2), encoding="utf-8")
        frames = project.duration_frames()
        cmd = [
            "npx", "remotion", "render", "remotion/src/index.tsx", "Documentary",
            str(rendered), "--props", str(props), "--frames", f"0-{frames - 1}",
        ]
        print("Rendering:", " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)

        narration = Path(args.narration) if args.narration else _find_narration(project_path, ROOT)
        if narration and not narration.is_absolute():
            narration = ROOT / narration
        music = Path(args.music) if args.music else _find_music(ROOT)
        if music and not music.is_absolute():
            music = ROOT / music
        if narration:
            mix(narration, music, audio_mix)
            _ffmpeg_audio(rendered, audio_mix, with_audio)
        else:
            _ffmpeg_audio(rendered, None, with_audio)

        srt = Path(args.srt) if args.srt else None
        if srt and not srt.is_absolute():
            srt = ROOT / srt
        if args.transcript:
            transcript = Path(args.transcript)
            if not transcript.is_absolute():
                transcript = ROOT / transcript
            data = json.loads(transcript.read_text(encoding="utf-8"))
            srt = work / "captions.srt"
            words_to_srt(data.get("words", []), srt)
        if srt and srt.exists():
            _mux_srt(with_audio, srt, final)
        else:
            final = with_audio
        final.replace(out)

    report = probe(out)
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise SystemExit("FLVYT delivery QA failed")
    print(f"Rendered and QA-passed: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
