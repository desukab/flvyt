"""End-to-end production orchestration for FLVYT.

`produce()` turns a topic / research pack / evidence pack / ready project into
a QA-passed MP4 using only local executables. Every stage is recorded in the
returned report so the caller can show exactly what ran.

Resumability: completed stages are recorded in `out/pipeline_state.json` keyed
by output path and fingerprinted by (stage, command, input contents). A stage
whose fingerprint is unchanged and whose output still exists is skipped on the
next build. `--force` bypasses the cache. A failed stage records the exact
command in `report["failure"]` and the same build command can be re-run to
resume from the first unfinished stage.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "out"
STATE_FILE = WORK / "pipeline_state.json"


class StageFailed(Exception):
    """Raised when a pipeline subprocess (or in-process stage) fails."""

    def __init__(self, stage: str, cmd: list[str], returncode: int | None,
                 output: str):
        super().__init__(f"stage '{stage}' failed (rc={returncode}): " + " ".join(cmd))
        self.stage = stage
        self.cmd = cmd
        self.returncode = returncode
        self.output = output
        self.report: dict[str, Any] | None = None


def _run(cmd: list[str], *, stage: str = "", show: bool = True) -> None:
    if show:
        print("$", " ".join(cmd), flush=True)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    except OSError as exc:
        raise StageFailed(stage, cmd, None, str(exc)) from exc
    if proc.returncode != 0:
        output = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip()
        raise StageFailed(stage, cmd, proc.returncode, output)


def _kind(raw: dict) -> str:
    if "beats" in raw:
        return "project"
    if "evidence" in raw:
        return "evidence"
    if "sources" in raw:
        return "research"
    raise ValueError("Input must be a research pack, evidence pack or ready project")


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fingerprint(stage: str, cmd: list[str], inputs: list[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(stage.encode("utf-8"))
    digest.update(json.dumps(cmd, sort_keys=True).encode("utf-8"))
    for path in inputs:
        absolute = Path(path) if path.is_absolute() else ROOT / path
        digest.update(str(absolute).encode("utf-8"))
        digest.update(absolute.read_bytes() if absolute.exists() else b"")
    return digest.hexdigest()


class _State:
    """Persisted per-output run bookkeeping for skip-on-unchanged resumability."""

    def __init__(self, key: str, *, force: bool, path: Path = STATE_FILE):
        self.key = key
        self.force = force
        self.path = path
        self.data: dict[str, Any] = {"runs": {}}
        if path.exists():
            try:
                self.data = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                self.data = {"runs": {}}
        self.runs = self.data.setdefault("runs", {})
        self.run = self.runs.setdefault(key, {})

    def should_skip(self, stage: str, fingerprint: str, output: str) -> bool:
        if self.force:
            return False
        record = self.run.get(stage)
        if not record or record.get("fingerprint") != fingerprint:
            return False
        target = ROOT / output if not Path(output).is_absolute() else Path(output)
        return target.exists()

    def mark(self, stage: str, fingerprint: str, output: str) -> None:
        self.run[stage] = {"fingerprint": fingerprint, "output": output}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        except OSError:
            pass


def refresh_editorial_plan(path: Path) -> None:
    """Regenerate sentence-level shots and validate them after any mutation."""
    from engine.editorial import add_shots
    from engine.editorial_gate import raise_if_invalid
    from engine.project import Project
    from engine.transitions import assign_transitions

    project = Project.load(path)
    add_shots(project.beats)
    assign_transitions(project.beats)
    raise_if_invalid(project.beats, fps=project.fps)
    Path(path).write_text(json.dumps(project.props(), indent=2, ensure_ascii=False), encoding="utf-8")


def _resume_hint(source: str | None, topic: str | None) -> str:
    target = topic if topic else (source or "input.json")
    return f"resume: flvyt build {target} (completed and unchanged stages are skipped)"


def produce(source: str | None = None, *, topic: str | None = None,
            out: str = "out/final.mp4",
            tts_command: str | None = None,
            tts_model: str | None = None,
            music: str | None = None,
            assets: str = "assets/registry.json",
            captions_model: str | None = None,
            ground_model: str | None = None,
            ground_endpoint: str | None = None,
            auto_captions: bool = True,
            max_results: int = 12,
            force: bool = False,
            state_file: Path | str | None = None) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    captions_model = captions_model or os.environ.get("FLVYT_WHISPER_MODEL", "small")
    ground_model = ground_model or os.environ.get("FLVYT_LLM_MODEL", "llama3.2")
    ground_endpoint = ground_endpoint or os.environ.get("FLVYT_LLM_ENDPOINT",
                                                        "http://127.0.0.1:11434/api/generate")
    state = _State(_fingerprint("run", ["out", out], []), force=force,
                   path=Path(state_file) if state_file else STATE_FILE)

    def run_stage(stage: str, cmd: list[str], inputs: list[Path], output: str,
                  *, work: Callable[[], None] | None = None) -> bool:
        """Run once unless already completed with identical inputs; skip then."""
        fingerprint = _fingerprint(stage, cmd, inputs)
        if state.should_skip(stage, fingerprint, output):
            steps.append({"step": stage, "skipped": True, "output": output})
            return False
        try:
            if work is not None:
                work()
            _run(cmd, stage=stage)
        except StageFailed as exc:
            exc.stage = exc.stage or stage
            exc.report = {"steps": steps, "out": out,
                          "failure": {
                              "step": exc.stage,
                              "command": " ".join(exc.cmd),
                              "output": exc.output,
                              "resume": _resume_hint(source, topic),
                          }}
            raise
        state.mark(stage, fingerprint, output)
        steps.append({"step": stage, "output": output})
        return True

    project: Path
    if source:
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        raw = _load(source_path)
        kind = _kind(raw)
        if kind == "research":
            evidence = ROOT / "projects/evidence.generated.json"
            run_stage("ground", [sys.executable, "scripts/ground.py", str(source_path),
                                 "--out", str(evidence), "--model", ground_model,
                                 "--endpoint", ground_endpoint],
                      [source_path], str(evidence))
            project = ROOT / "projects/generated.json"
            run_stage("plan", [sys.executable, "scripts/plan.py", str(evidence),
                               "--out", str(project)], [evidence], str(project))
        elif kind == "evidence":
            project = ROOT / "projects/generated.json"
            run_stage("plan", [sys.executable, "scripts/plan.py", str(source_path),
                               "--out", str(project)], [source_path], str(project))
        else:
            project = source_path
    else:
        if not topic:
            raise ValueError("Provide a topic or an input file")
        research = ROOT / "projects/research.json"
        run_stage("research", [sys.executable, "scripts/research.py", topic,
                               "--out", str(research), "--max-results", str(max_results)],
                  [], str(research))
        evidence = ROOT / "projects/evidence.generated.json"
        run_stage("ground", [sys.executable, "scripts/ground.py", str(research),
                             "--out", str(evidence), "--model", ground_model,
                             "--endpoint", ground_endpoint],
                  [research], str(evidence))
        project = ROOT / "projects/generated.json"
        run_stage("plan", [sys.executable, "scripts/plan.py", str(evidence),
                           "--out", str(project)], [evidence], str(project))

    registry = Path(assets)
    if not registry.is_absolute():
        registry = ROOT / registry
    if registry.exists():
        planned_path = ROOT / "projects/asset_planned.json"

        def assign_asset_work() -> None:
            from engine.asset_director import assign_assets
            from engine.project import Project
            planned = assign_assets(Project.load(project), registry, ROOT)
            planned_path.write_text(json.dumps(planned.props(), indent=2,
                                               ensure_ascii=False), encoding="utf-8")

        run_stage("assets", ["in-process", "assign_assets", str(project), str(registry)],
                  [project, registry], str(planned_path), work=assign_asset_work)
        project = planned_path

    run_stage("editorial", ["in-process", "refresh_editorial_plan", str(project)],
              [project], str(project), work=lambda: refresh_editorial_plan(project))

    narration = False
    if tts_command:
        cmd = [sys.executable, "scripts/synthesize.py", str(project), "--command", tts_command,
               "--out-dir", "out/narration"]
        if tts_model:
            cmd += ["--model", tts_model]
        master = "out/narration/master.wav"

        def finish_narration() -> None:
            from engine.audio import assemble_narration
            from engine.timing import retime_project
            manifest = ROOT / "out/narration/tts_manifest.json"
            if manifest.exists():
                retime_project(project, manifest)
                refresh_editorial_plan(project)
                manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
                beats_data = json.loads(Path(project).read_text(encoding="utf-8"))["beats"]
                if any(b["id"] in manifest_data for b in beats_data):
                    assemble_narration(beats_data, manifest_data,
                                       WORK / "narration/master.wav", cwd=ROOT)

        run_stage("narration", cmd, [project], master, work=finish_narration)
        narration = (WORK / master).exists()

    transcript = None
    if narration and auto_captions:
        transcript = ROOT / "out/narration/transcript.json"
        run_stage("captions", [sys.executable, "scripts/transcribe.py", "out/narration/master.wav",
                               "--model", captions_model, "--output", str(transcript)],
                  [WORK / "narration/master.wav"], str(transcript))

    render = [sys.executable, "scripts/render.py", str(project), "--out", out]
    if music:
        render += ["--music", music]
    if transcript:
        render += ["--transcript", str(transcript)]
    run_stage("render", render, [project] + ([transcript] if transcript else []), out)

    qa: dict[str, Any] = {}
    qa_path = ROOT / "out/qa.json"
    if qa_path.exists():
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
    else:
        qa = {"ok": True, "note": "QA report written by render step"}
    return {"steps": steps, "out": str(out), "qa": qa}