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
from engine.audio import assemble_narration, mix
from engine.director import direct
from engine.project import Project
from engine.quality import probe, probe_frames, probe_delivery
from engine.score import render_bed
from engine.captions import words_to_srt
from engine.editorial_quality import report_to_path as editorial_report_to_path
from engine.manifest import write_manifest


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


def _project_provenance(project_path: Path) -> dict | None:
    """Grounding provenance carried from the plan into the manifest, if any."""
    try:
        raw = json.loads(Path(project_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    provenance = raw.get("provenance")
    return provenance if isinstance(provenance, dict) else None


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
        project = Project.load(project_path)
        beats_data = project.props()["beats"]
        if beats_data:
            return assemble_narration(beats_data, data, root / "out/narration/master.wav", cwd=root)
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
        editorial_qa = editorial_report_to_path(props, ROOT / "out/editorial_qa.json")
        print("Editorial QA:", json.dumps(
            {"ok": editorial_qa["ok"], "fails": len(editorial_qa["fails"]),
             "warns": len(editorial_qa["warns"])}))
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
        music_info: dict | None = None
        music = Path(args.music) if args.music else _find_music(ROOT)
        if music and not music.is_absolute():
            music = ROOT / music
        if not music and narration:
            total = project.duration_frames() / max(float(project.fps or 30), 1)
            music_info = render_bed(total, project.props()["beats"], work / "bed.wav")
            music = Path(music_info["wav"])
        if narration:
            mix(narration, music, audio_mix)
            _ffmpeg_audio(rendered, audio_mix, with_audio)
        else:
            music = None
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
        narration_info = narration and {"wav": str(narration)}
        caption_info = (srt is not None and srt.exists() and {"srt": str(srt)}) or (
            args.transcript and {"transcript": args.transcript})

    report = probe(out)
    print(json.dumps(report, indent=2))
    frame_report = probe_frames(out)
    print("Frame QA:", json.dumps(
        {"ok": frame_report["ok"], "fails": frame_report["fails"]}))
    delivery = probe_delivery(out, expect_narration=narration is not None)
    print("Delivery QA:", json.dumps(
        {"ok": delivery["ok"], "fails": delivery["fails"]}))
    qa_out = ROOT / "out/qa.json"
    qa_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.write_text(json.dumps(
        {"ok": bool(report.get("ok") and editorial_qa.get("ok")
                  and frame_report.get("ok") and delivery.get("ok")),
         "ffprobe": report, "signalstats": frame_report,
         "delivery": {k: v for k, v in delivery.items()
                      if k not in {"fails", "warns", "ok"}}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    write_manifest(
        project_path, ROOT / "out/manifest.json", report, editorial_qa,
        root=ROOT,
        narration=narration_info,
        captions=caption_info,
        assets={"evidence": _project_provenance(project_path)},
        render={
            "fps": project.fps, "width": project.width, "height": project.height,
            "frames": frames, "out": str(out),
        },
        frameqa=frame_report,
        edit_qa={k: v for k, v in delivery.items()
                 if k not in {"fails", "warns", "ok"}},
        music=music_info or {},
    )
    if not report.get("ok"):
        raise SystemExit("FLVYT delivery QA failed")
    if not editorial_qa.get("ok"):
        detail = "; ".join("FAIL: %s" % f for f in (editorial_qa.get("fails") or [])[:8])
        if editorial_qa.get("warns"):
            detail += " | " + "; ".join("WARN: %s" % w for w in (editorial_qa.get("warns") or [])[:8])
        raise SystemExit("FLVYT editorial quality QA failed\n- " + detail)
    if not frame_report.get("ok"):
        raise SystemExit("FLVYT frame-level QA failed")
    if not delivery.get("ok"):
        raise SystemExit("FLVYT delivery edit QA failed\n- " + "\n- ".join((delivery.get("fails") or [])[:8]))
    print(f"Rendered and QA-passed: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
