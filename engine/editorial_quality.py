"""Machine-readable editorial quality analysis for documentary projects.

This report turns a planned project (beats + shots), optional narration manifest
and optional whisper transcript into a set of named, thresholded metrics. It is
the visual-quality counterpart to :mod:`engine.quality` (which checks the
delivered MP4). Everything runs on the *plan*, so it can catch a monotonous,
cramped or unbalanced edit before a single frame is rendered.

The report shape is stable on purpose:

    {
      "ok": bool,
      "fails": [str],
      "warns": [str],
      "metrics": {name: {"value": ...,
                         "unit": ..., "limit": ..., "ok": bool, "detail": str}},
      "project": str,
      "engine": str,
    }
"""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

ENGINE_VERSION = "flvyt-engine-2.0"

# Reading budget: even a fast reader tops out near 16 characters per second on a
# primary headline. Dense factual captions sit comfortably below that.
WARN_CHARS_PER_SECOND = 16
UNREADABLE_CHARS_PER_SECOND = 22
MIN_SHOT_SECONDS = 1.0
MAX_SHOT_SECONDS = 12.0
VISUAL_RUN_FAIL = 4
VISUAL_RUN_WARN = 3
NEAR_DUP_OVERLAP = 0.85
MIN_NONCUTS_BEFORE_CHAPTER_WARN = 3
CHAPTER_GAP_WARN_SECONDS = 150.0
ASSET_OVERUSE = 4
MAX_CAPTION_CUES_PER_MINUTE = 14
MAX_CAPTION_CUE_SECONDS = 5.0
MIN_NARRATION_COVERAGE = 0.5


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _token_set(text: str) -> set[str]:
    return {t for t in text.lower().split() if len(t) > 3}


def _overlap(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def _metric(name: str, value: Any, unit: str, limit: str,
            ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "value": value, "unit": unit, "limit": limit,
            "ok": ok, "detail": detail}


def _shot_refs(shots_and_beats: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    # Shots carry only intra-beat ids ("s1"); surface them as beat/shot so
    # messages point at exactly one place in the plan.
    return {id(s): f"{b.get('id')}/{s.get('id')}"
            for s, b in shots_and_beats}


def emit(metrics: dict[str, dict[str, Any]], fails: list[str],
         warns: list[str], project: str) -> dict[str, Any]:
    return {
        "ok": not fails,
        "fails": fails,
        "warns": warns,
        "metrics": metrics,
        "project": str(project),
        "engine": ENGINE_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def analyze(project_path: str | Path, manifest_path: str | Path | None = None,
            transcript_path: str | Path | None = None) -> dict[str, Any]:
    """Analyze a planned project and return the editorial quality report."""
    project = _load(project_path)
    beats = project.get("beats", [])
    fps = float(project.get("fps", 30))
    fails: list[str] = []
    warns: list[str] = []
    metrics: dict[str, dict[str, Any]] = {}

    if not beats:
        return emit(metrics, ["project has no beats"], warns, project_path)

    shots_with_beat = [(s, b) for b in beats for s in b.get("shots", [])]
    shots = [s for s, _ in shots_with_beat]
    refs = _shot_refs(shots_with_beat)
    total_seconds = 5.0 + sum(max(0.5, float(b.get("seconds", 0))) for b in beats)
    shot_seconds = [float(s.get("seconds", 0)) for s in shots]

    # --- Shot-duration distribution -----------------------------------------
    ok_dist = True
    shots_short = [s for s in shots if float(s.get("seconds", 0)) < MIN_SHOT_SECONDS]
    shots_long = [s for s in shots if float(s.get("seconds", 0)) > MAX_SHOT_SECONDS]
    if shots_short:
        ok_dist = False
        fails.append(f"shot duration below {MIN_SHOT_SECONDS}s: "
                     + ", ".join(refs[id(s)] for s in shots_short[:8]))
    if shots_long:
        ok_dist = False
        fails.append(f"shot duration exceeds {MAX_SHOT_SECONDS}s: "
                     + ", ".join(refs[id(s)] for s in shots_long[:8]))
    dist = ""
    if shot_seconds:
        dist = (
            f"min {min(shot_seconds):.2f}s median {statistics.median(shot_seconds):.2f}s "
            f"mean {statistics.mean(shot_seconds):.2f}s max {max(shot_seconds):.2f}s "
            f"stdev {statistics.pstdev(shot_seconds):.2f}s"
        )
    metrics["shot_duration_distribution"] = _metric(
        "shot_duration_distribution", dist, "seconds",
        f"{MIN_SHOT_SECONDS}-{MAX_SHOT_SECONDS}s", ok_dist,
        f"{len(shots)} shots across {total_seconds:.1f}s")
    buckets = [0, 0, 0, 0]
    for sec in shot_seconds:
        if sec < 2.0:
            buckets[0] += 1
        elif sec < 3.5:
            buckets[1] += 1
        elif sec < 5.0:
            buckets[2] += 1
        else:
            buckets[3] += 1
    metrics["shot_duration_buckets"] = _metric(
        "shot_duration_buckets",
        {"lt2": buckets[0], "2-3.5": buckets[1], "3.5-5": buckets[2], "gt5": buckets[3]},
        "shots", "spread", True,
        f"<2s:{buckets[0]} 2-3.5s:{buckets[1]} 3.5-5s:{buckets[2]} >5s:{buckets[3]}")

    # --- Text density and underfilled frames --------------------------------
    def _density(s: dict[str, Any]) -> float:
        sec = float(s.get("seconds", 0))
        return len(str(s.get("text", ""))) / sec if sec > 0 else 0.0

    dense = [s for s in shots if _density(s) > WARN_CHARS_PER_SECOND]
    unreadable = [s for s in shots if _density(s) > UNREADABLE_CHARS_PER_SECOND]
    empty = [s for s in shots if not str(s.get("text", "")).strip()]
    if unreadable:
        fails.append(f"text density above {UNREADABLE_CHARS_PER_SECOND} chars/s on "
                     + ", ".join(refs[id(s)] for s in unreadable[:8]))
    if dense:
        warns.append(f"dense (>{WARN_CHARS_PER_SECOND} chars/s) on "
                     + ", ".join(refs[id(s)] for s in dense[:8]))
    if empty:
        fails.append("shots carry no text: " + ", ".join(refs[id(s)] for s in empty[:8]))
    max_density = max((_density(s) for s in shots), default=0.0)
    metrics["text_density"] = _metric(
        "text_density", round(max_density, 2), "chars/second",
        f"<= {WARN_CHARS_PER_SECOND} (warn), u-readable <= {UNREADABLE_CHARS_PER_SECOND} (fail)",
        not unreadable,
        f"{len(unreadable)} unreadable, {len(dense)} dense")

    # --- Repetition detection -----------------------------------------------
    # Re-echoing one sentence across a beat's own establish→hold shots is the
    # deliberate "single thought" editorial shape. Repetition only counts as a
    # defect when it crosses a beat boundary: a second beat repeating an earlier
    # beat's wording is something a viewer actually perceives.
    beat_for = {id(s): b.get("id") for s, b in shots_with_beat}
    texts = [str(s.get("text", "")) for s in shots]
    for i in range(1, len(texts)):
        if (texts[i] and texts[i] == texts[i - 1]
                and beat_for[id(shots[i])] != beat_for[id(shots[i - 1])]):
            fails.append("identical text repeated across beats: "
                         f"{refs[id(shots[i])]} == {refs[id(shots[i-1])]}")
            break
    near = []
    for i in range(1, len(texts)):
        if (texts[i - 1] and texts[i]
                and beat_for[id(shots[i])] != beat_for[id(shots[i - 1])]
                and _overlap(texts[i - 1], texts[i]) >= NEAR_DUP_OVERLAP):
            near.append(f"{refs[id(shots[i-1])]}~{refs[id(shots[i])]}")
    if near:
        warns.append(f"near-duplicate adjacent text ({(NEAR_DUP_OVERLAP*100):.0f}%+ overlap): "
                     + ", ".join(near[:8]))
    metrics["near_duplicate_pairs"] = _metric(
        "near_duplicate_pairs", len(near), "pairs",
        f"= 0", len(near) == 0, " vs ".join(near[:6]) or "none")

    # --- Visual variety and montage streaks ---------------------------------
    visuals = [str(s.get("visual", "")) for s in shots]
    vcount = Counter(visuals)
    longest_run = 0
    run = 0
    worst_run = ("", 0)
    for i, v in enumerate(visuals):
        run = run + 1 if i and v == visuals[i - 1] else 1
        if run > longest_run:
            longest_run = run
            worst_run = (v, i - run + 1)
    if len(visuals) >= VISUAL_RUN_FAIL and longest_run >= VISUAL_RUN_FAIL:
        fails.append(f"{longest_run}x consecutive '{worst_run[0]}' shots "
                     f"(shots {worst_run[1]+1}..{worst_run[1]+longest_run}): "
                     f"the montage is stalling")
    elif longest_run >= VISUAL_RUN_WARN:
        warns.append(f"{longest_run}x consecutive '{worst_run[0]}' shots "
                     f"(shots {worst_run[1]+1}..{worst_run[1]+longest_run})")
    variety = len(vcount)
    metrics["visual_variety"] = _metric(
        "visual_variety", {k: v for k, v in sorted(vcount.items(), key=lambda x: -x[1])},
        "shots", "distinct visuals", variety >= 3,
        f"{variety} distinct visuals; longest run {longest_run} ({worst_run[0]})")
    if variety < 3:
        warns.append(f"only {variety} distinct visuals across the edit")

    # --- Transition density --------------------------------------------------
    noncuts = [s for s in shots if str(s.get("transition", "cut")) != "cut"]
    per_minute = len(noncuts) / max(1e-9, total_seconds / 60.0)
    metrics["transition_density"] = _metric(
        "transition_density", round(per_minute, 2), "non-cuts/minute",
        "0 defaults to cut grammar", True,
        f"{len(noncuts)} non-cut transitions of {len(shots)} shots")
    if total_seconds > 90 and len(noncuts) < MIN_NONCUTS_BEFORE_CHAPTER_WARN:
        warns.append("very few non-cut transitions: nothing marks chapter or "
                     "thesis boundaries")

    # --- Emphasis distribution ----------------------------------------------
    emf = Counter(str(b.get("emphasis", "normal")) for b in beats)
    metrics["emphasis_distribution"] = _metric(
        "emphasis_distribution", dict(emf), "beats", "mixed emphasis", True,
        f"{len(beats)} beats")
    if len(emf) == 1 and len(beats) >= 6:
        warns.append(f"every beat is emphasis='{list(emf)[0]}': the edit never "
                     "rises or falls")

    # --- Chapter pacing ------------------------------------------------------
    sections = [b for b in beats if str(b.get("kind")) == "section"]
    evidence_beats = [b for b in beats if str(b.get("kind")) == "evidence"]
    first_evidence_at = 0.0
    if evidence_beats:
        first_evidence_at = sum(max(0.5, float(b.get("seconds", 0)))
                                for b in beats[:beats.index(evidence_beats[0])])
    kinds = [str(b.get("kind")) for b in beats]
    run = 0
    longest_kind_run = 0
    worst_kind = ""
    for i, k in enumerate(kinds):
        run = run + 1 if i and k == kinds[i - 1] else 1
        if run > longest_kind_run:
            longest_kind_run = run
            worst_kind = k
    chapter_pacing_ok = bool(sections) or len(beats) < 10
    chapter_note = ""
    if sections:
        gaps = []
        last = 0.0
        for b in beats:
            if str(b.get("kind")) == "section":
                gaps.append(last)
                last = 0.0
            else:
                last += max(0.5, float(b.get("seconds", 0)))
        if any(g > CHAPTER_GAP_WARN_SECONDS for g in gaps):
            warns.append(f"chapter gap of {max(gaps):.0f}s exceeds "
                         f"{CHAPTER_GAP_WARN_SECONDS:.0f}s")
        chapter_note = f"{len(sections)} chapter(s); slowest chapter {max(gaps + [0.0]):.0f}s"
    metrics["chapter_pacing"] = _metric(
        "chapter_pacing",
        {"sections": len(sections), "first_evidence_after": round(first_evidence_at, 1),
         "longest_kind_run": longest_kind_run, "kind": worst_kind},
        "chapters", "evidence within minutes of an opener", chapter_pacing_ok, chapter_note)
    if len(beats) >= 10 and not sections:
        warns.append("long documentary has no chapter/section markers")

    # --- Asset reuse ---------------------------------------------------------
    usage: Counter = Counter()
    for b in beats:
        src = str(b.get("assetSrc", "") or "")
        if src:
            usage[src] += 1
    over = {k: v for k, v in usage.items() if v > ASSET_OVERUSE}
    if over:
        warns.append("asset reuse: " + ", ".join(f"{k.split('/')[-1]}x{v}"
                                                 for k, v in over.items()))
    metrics["asset_reuse"] = _metric(
        "asset_reuse", dict(usage), "beats per asset",
        f"<= {ASSET_OVERUSE}", not over,
        f"{len(usage)} distinct assets in {len(beats)} beats")

    # --- Narration / visual alignment ---------------------------------------
    if manifest_path and Path(manifest_path).exists():
        manifest = _load(manifest_path)
        from .audio import duration as audio_duration
        drift = 0.0
        misaligned = []
        narrated = 0
        for b in beats:
            audio = manifest.get(str(b.get("id")))
            if not audio:
                continue
            narrated += 1
            pad = float(b.get("pad_after", 0) or 0)
            visual = float(b.get("seconds", 0))
            try:
                adur = audio_duration(audio)
            except Exception:
                continue
            if visual + 1e-9 < adur - 0.1:
                misaligned.append(str(b.get("id")))
            drift += abs(visual - (adur + pad))
        if misaligned:
            warns.append("narration longer than its visual on: "
                         + ", ".join(misaligned[:8]))
        metrics["narration_alignment"] = _metric(
            "narration_alignment", round(drift, 2), "seconds drift",
            "visual >= narration", not misaligned,
            f"{narrated}/{len(beats)} beats narrated")
    else:
        metrics["narration_alignment"] = _metric(
            "narration_alignment", "unavailable", "seconds", "manifest required",
            True, "no narration manifest supplied")

    # --- Caption density -----------------------------------------------------
    if transcript_path and Path(transcript_path).exists():
        transcript = _load(transcript_path)
        cues = transcript.get("cues") or []
        words = transcript.get("words") or []
        if cues:
            cue_seconds = [float(c.get("end", 0)) - float(c.get("start", 0)) for c in cues]
            long_cues = [round(c, 2) for c in cue_seconds if c > MAX_CAPTION_CUE_SECONDS]
            covered = max((float(c.get("end", 0)) for c in cues), default=0.0)
            coverage = covered / max(1e-9, total_seconds)
            per_min = len(cues) / max(1e-9, total_seconds / 60.0)
            caption_ok = per_min <= MAX_CAPTION_CUES_PER_MINUTE and not long_cues
            if long_cues:
                warns.append(f"caption cues exceed {MAX_CAPTION_CUE_SECONDS}s: {long_cues[:8]}")
            if per_min > MAX_CAPTION_CUES_PER_MINUTE:
                warns.append(f"caption density {per_min:.0f} cues/min exceeds "
                             f"{MAX_CAPTION_CUES_PER_MINUTE}")
            if coverage < MIN_NARRATION_COVERAGE:
                warns.append(f"captions cover only {coverage*100:.0f}% of the video")
            metrics["caption_density"] = _metric(
                "caption_density",
                {"cues": len(cues), "cues_per_minute": round(per_min, 1),
                 "max_cue_seconds": round(max(cue_seconds, default=0), 2),
                 "coverage": round(coverage, 3), "words": len(words)},
                "cues", f"<= {MAX_CAPTION_CUES_PER_MINUTE}/min", caption_ok,
                f"{len(cues)} cues, {len(words)} words, {coverage*100:.0f}% coverage")
        else:
            metrics["caption_density"] = _metric(
                "caption_density", 0, "cues", ">= 1 cue", False, "transcript has no cues")
            warns.append("transcript provided but no caption cues could be built")
    else:
        metrics["caption_density"] = _metric(
            "caption_density", "unavailable", "cues", "transcript required", True,
            "no transcription supplied")

    return emit(metrics, fails, warns, project_path)


def report_to_path(project_path: str | Path, out_path: str | Path,
                   manifest_path: str | Path | None = None,
                   transcript_path: str | Path | None = None) -> dict[str, Any]:
    """Analyze and write the machine-readable report to `out_path`."""
    report = analyze(project_path, manifest_path=manifest_path,
                     transcript_path=transcript_path)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def render_text(report: dict[str, Any]) -> str:
    """Human-readable rendering of the editorial quality report."""
    lines = [f"FLVYT editorial quality report ({report.get('engine')})",
             f"project: {report.get('project')}", ""]
    for key in sorted(report.get("metrics", {})):
        m = report["metrics"][key]
        mark = "[ok] " if m["ok"] else "[warn]"
        lines.append(f" {mark} {key:28} {str(m['value'])[:90]}")
    lines.append("")
    for f in report.get("fails", []):
        lines.append(f" FAIL: {f}")
    for w in report.get("warns", []):
        lines.append(f" WARN: {w}")
    lines.append("")
    lines.append("EDITORIAL QA: "
                 + ("PASS" if report.get("ok") else "FAILED")
                 + f" ({len(report.get('fails', []))} fails, "
                   f"{len(report.get('warns', []))} warns)")
    return "\n".join(lines)