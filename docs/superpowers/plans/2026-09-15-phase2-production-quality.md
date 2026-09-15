# Phase 2: Production-Quality Documentary System — Implementation Plan

**Goal:** Turn the deterministic 3:37 TSMC fixture baseline into a channel-ready
automated documentary production system: visual QA, editorial-brain upgrades,
Remotion polish, a second verified fixture with a different topic/structure,
resumable+failure-recovering pipeline, production manifest, better doctor, and
real local TTS verification.

**Architecture:** Everything stays dependency-free Python (stdlib) with local
executables (ffmpeg/ffprobe, node/remotion, espeak TTS). Planning is
deterministic; QA is machine-readable JSON written to `out/`. Rendering remains
CI-validated (Remotion cannot run under Termux/Android); every other stage is
verifiable locally.

**Tech Stack:** Python 3.12+ stdlib, Remotion/React TSX, FFmpeg, espeak TTS.

**Spec:** This plan (from the user's PHASE 2 — PRODUCTION QUALITY list, items 1–20).

## Global Constraints
- Never rewrite working infrastructure; edit in place and extend.
- No auto-scraping of copyrighted footage; no paid APIs; verified sources only.
- Both fixtures must pass: source grounding, editorial gate, rendering, audio,
  caption, delivery QA, visual quality QA, and now editorial quality QA.
- All changes: inspect → implement → test → fix → commit → push → verify CI.
- Downstream contract: `Beat.seconds` is the single source of truth for runtime;
  the renderer must never silently shorten it.

---

## Task P2-1: Editorial quality engine (`engine/editorial_quality.py`)
Machine-readable metrics over a project JSON (beats+shots), optional narration
manifest and optional transcript. Produces `{ok, fails, warns, metrics}`.
Metrics required: shot-duration distribution; repetition (text repeats, near-dup
pairs, visual-run streaks); transition density; text density; empty/underfilled
frames; visual variety; emphasis distribution; caption density; narration
alignment; chapter pacing; asset reuse frequency.

## Task P2-2: Wire QA into pipeline + production manifest
`produce()` and `render.py` write `out/editorial_qa.json` and `out/manifest.json`
(seed, engine version, software versions, inputs, assets/licenses, narration,
captions, render settings, QA). `flvyt.py` prints a QA summary line.

## Task P2-3: Editorial brain upgrades (chapters + expected-beat spacing)
New beat kind `section` + visual `chapter`. `story.py` accepts optional
`chapter`/`chapter_title` per evidence and inserts chapter-opening section beats.
Editorial/editorial_gate/edit_policy/transitions learn `section`/`chapter`.
Fixes QA-exposed weak patterns (claim-card monotony, lack of chapter pacing).

## Task P2-4: Remotion visual polish
Fit-to-container typography (no overflow, safe areas), continuous motion on
holds (no slideshow), chart baseline/labels, timeline year labels, map legend,
statistic emphasis pulse, quote card refinement, chapter openings (ChapterVisual),
dip polish. Typecheck must stay green.

## Task P2-5: Second verified fixture — submarine communications cables
`projects/evidence.cables.json` (chaptered pack, ~50 items, all citing the
live Wikipedia "Submarine communications cable" article) + committed
`projects/cables.generated.json` (4 chapters, timeline/map/stat-heavy structure).
`tests/test_fixture_cables.py` guards. New CI job renders + uploads artifact.

## Task P2-6: Frame-level video QA
`engine/quality.py::frames_report(path)` using ffmpeg `signalstats` to detect
near-black/underfilled frames. `acceptance.py` includes it in delivery QA.

## Task P2-7: Doctor upgrade
Per-stage statuses REQUIRED/OPTIONAL/CONFIGURED/MISSING plus per-stage mapping
and clear missing-tool guidance. Backwards-compatible with `summarize()`.

## Task P2-8: Resumability
`engine/pipeline.py` keeps `out/pipeline_state.json` with per-stage input
fingerprints; completed+unchanged stages are skipped. `--force` bypasses.

## Task P2-9: Failure recovery
`_run` captures output; stage failures produce `report["failure"]` with the
exact failed command and the resume invocation; `flvyt` prints it.

## Task P2-10: CI caching
`actions/setup-node` cache for npm in the render/acceptance jobs (safe).

## Task P2-11: Real local pipeline verification
espeak TTS synthesizes real narration locally; audio assembly + editorial QA +
manifest verified on-device; whisper/render documented as the two stages
(external whisper package, Remotion Android binding) requiring a real Linux host.
`flvyt doctor` reports exactly this.

## Task P2-12: Docs + final verification
README updates for Phase 2; package.json scripts; final full test + typecheck +
CI green across both fixtures.