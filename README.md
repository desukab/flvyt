# FLVYT

Production-oriented automated faceless technology-documentary engine.

## What this is

FLVYT is **not another video editor written from scratch**. It is the editorial brain and orchestration layer sitting on top of proven video infrastructure.

```text
Topic
  ↓
Local web research
  ↓
Source-grounded evidence
  ↓
Documentary beats
  ↓
Editorial director
  ↓
License-cleared asset matching
  ↓
Local narration + audio-driven timing
  ↓
Remotion motion graphics / B-roll treatment
  ↓
FFmpeg mix + captions + delivery mux
  ↓
Technical QA
  ↓
FINAL MP4
```

The target is a serious faceless technology channel: controlled pacing, visual hierarchy, charts/maps/timelines, documentary typography and repeatable motion — without manually editing a timeline.

## Production components

- **video-autopilot-kit** — MIT-licensed reusable production gates, media helpers, audio chain, captions and QA.
- **Remotion 4.0.524** — programmatic React video rendering and motion graphics.
- **FFmpeg** — local audio/video processing and final delivery.
- **faster-whisper (optional/local)** — word and segment timestamps for automatic captions.
- **Piper, espeak-ng or another locally installed TTS engine** — local narration with no paid API requirement.
- **ddgs + Trafilatura (optional/local)** — no-key web discovery and readable source extraction.
- **Ollama-compatible local LLM (optional/local)** — source-grounded evidence generation without a paid API.

Every tool is checked by description, not assumption: `flvyt doctor` reports each one as `REQUIRED`/`OPTIONAL` with a `CONFIGURED`/`MISSING` status, the pipeline stage it powers, and an exact install hint when a required tool is absent. Runs entirely locally; Termux on-device is fully supported for everything except the two Linux-host stages (Remotion rendering and faster-whisper transcription), for which the doctor and docs point at the standard GitHub-Actions Ubuntu pipeline.

## One-command production build

Requirements: Python 3.10+, Node 20+, FFmpeg (with `ffprobe`). For the fully automated local workflow, install the optional research/transcription dependencies and run a local TTS engine and Ollama-compatible model.

```bash
npm install
python scripts/bootstrap_upstream.py
python -m pip install -r requirements-research.txt
python -m pip install -r requirements-local.txt
python -m compileall engine scripts
npm run typecheck
flvyt doctor   # see exactly which local tools are present vs missing
```

### The `flvyt` CLI

A single entry point drives the whole local pipeline and checks the environment:

```bash
flvyt "How TSMC became indispensable to advanced computing"   # research → MP4
flvyt build projects/evidence.example.json                     # verified pack → MP4
flvyt plan projects/evidence.example.json                      # evidence → beats
flvyt render projects/generated.json                           # beats → MP4
flvyt ingest intro "public/intro.mp4"                          # add a licensed asset
flvyt doctor                                                   # preflight tools
```

`flvyt <topic>` runs research, source-grounded evidence, story planning, asset matching (when a registry exists), narration, narration-driven timing, captions (when available), Remotion rendering and delivery QA. It stops with a clear message rather than fabricating facts when a required optional stage (for example the local grounding model) is missing.

Builds are **resumable**. Completed stages are recorded in `out/pipeline_state.json` keyed by output path and fingerprinted by stage + command + input contents; re-running the same build skips every stage that finished unchanged, and `--force` re-runs everything from scratch. When a stage fails, FLVYT prints the exact failing command, its captured output and the resume invocation, so a transient network or tool failure is a one-command recovery.

### From a topic to a video

1. Collect candidate sources and ground them through a local model in one step:

```bash
export FLVYT_TTS_COMMAND='piper --model {model} --output_file {output}'
export FLVYT_TTS_MODEL=/path/to/voice.onnx
flvyt "How TSMC became indispensable to advanced computing"
```

The local grounding gate refuses evidence items whose source URL was not present in the collected research and refuses evidence without a supporting quote. The resulting evidence should still be reviewed before publishing.

The pipeline is also available directly through `scripts/build.py`, which accepts a research pack, an evidence pack or a ready project, with the same flags:

```bash
python scripts/build.py projects/research.json \
  --tts-command 'piper --model {model} --output_file {output}' \
  --tts-model /path/to/voice.onnx \
  --out out/final.mp4
```

The `flvyt` topic form reads those TTS settings from `FLVYT_TTS_COMMAND` / `FLVYT_TTS_MODEL`, so the command stays a single topic word (see the first example above).

On Termux, the same one-liner with espeak-ng produces real narration locally:

```bash
export FLVYT_TTS_COMMAND='espeak-ng -w {output}'
flvyt "How TSMC became indispensable to advanced computing"
```

Use `--force` to bypass the resume cache and run every stage, and simply re-run the printed build command to recover from any failed stage.

### From an already verified evidence pack

```bash
python scripts/build.py projects/evidence.example.json \
  --tts-command 'piper --model {model} --output_file {output}' \
  --tts-model /path/to/voice.onnx \
  --out out/final.mp4
```

Without narration, the same renderer can produce a valid video with a silent audio track:

```bash
python scripts/build.py projects/evidence.example.json --out out/final.mp4
```

The build performs story planning, asset matching when a registry is supplied, TTS synthesis, narration-driven beat timing, local transcription, captions, Remotion rendering, FFmpeg audio processing and delivery QA.

## Local dependencies

Everything runs locally. `flvyt doctor` prints a live checklist; `required` tools are mandatory, `optional` tools upgrade specific stages when installed. Never fabricate a fact to paper over a missing tool — the pipeline stops and tells you what to install.

| Tool | Required | Powers |
| --- | --- | --- |
| Python 3.10+ | yes | all editorial, audio, captioning and QA logic (stdlib-only core) |
| Node 20+ / npm | yes | Remotion 4 rendering of motion graphics |
| FFmpeg + ffprobe | yes | narration assembly, mixing, silent track fallback, delivery mux, QA |
| `ddgs` + `trafilatura` | no | no-key web source discovery and readable extraction (`requirements-research.txt`) |
| Ollama-compatible local LLM | no | source-grounding gate that turns research into evidence packs |
| local TTS executable | no | narration synthesis (any command accepting `{model}`/`{output}` — e.g. `espeak-ng -w {output}` on Termux) |
| faster-whisper | no | local word-timed transcription for automatic captions (`requirements-local.txt`) |
| asset registry | no | license-cleared B-roll selection; procedural visuals render without it |

Environment variables: `FLVYT_LLM_MODEL` / `FLVYT_LLM_ENDPOINT` (grounding, default `llama3.2` at Ollama's `api/generate`), `FLVYT_TTS_COMMAND` / `FLVYT_TTS_MODEL` (narration), `FLVYT_WHISPER_MODEL` (captions, default `small`).

## Evidence format

The preferred verified production input is an evidence pack. It keeps claims tied to sources rather than asking the renderer to invent facts.

```json
{
  "title": "How TSMC Became Indispensable",
  "thesis": "The world's most advanced chips depend on a manufacturing system few companies can reproduce.",
  "evidence": [
    {
      "id": "e01",
      "claim": "A verified factual claim from a source",
      "source": "https://example.com/source",
      "source_type": "article",
      "importance": "high",
      "tags": ["semiconductor", "manufacturing"]
    }
  ]
}
```

Use `scripts/plan.py` to turn this into executable documentary beats. FLVYT intentionally keeps the research trail attached to the relevant scenes.

## Local narration and automatic timing

FLVYT does not require a paid TTS provider. The TTS adapter accepts any local executable using `{model}` and `{output}` placeholders. Piper is one supported option. Review the license of the specific voice model before commercial use; the Piper software is MIT, while individual voice models can have their own licensing terms.

After synthesis, FLVYT measures each narration clip and retimes the corresponding visual beat. This prevents the common automated-video failure where narration and visuals drift apart.

## Captions

When TTS is enabled, `scripts/build.py` automatically assembles the narration, transcribes it with faster-whisper and muxes timed SRT captions into the MP4. Caption timestamps account for the documentary intro.

## Asset discipline

Every automated B-roll selection must come from a registry entry with an explicit license class:

- `owned`
- `public-domain`
- `cc0`
- `cc-by`
- `cc-by-sa`
- `licensed`

Example: `assets/registry.example.json`.

Local visual assets intended for Remotion live under `public/` and are referenced relative to that folder. FLVYT does **not** scrape arbitrary copyrighted B-roll or silently assume that a search result is reusable.

## Architecture boundary

FLVYT owns the **editorial intelligence**: research orchestration, grounding gates, beat planning, visual intent, timing, asset matching, reusable motion primitives and deterministic orchestration. Remotion owns programmatic visuals; FFmpeg and the reused upstream tooling own media processing, audio, captions and delivery gates.

## Validation

GitHub Actions validates both the Python layer and the Remotion/TypeScript layer on every push.

```bash
npm run test
npm run typecheck
npm run python-check
```

`scripts/acceptance.py` is the deterministic full-pipeline render gate: it generates per-beat narration with FFmpeg tones, retranscribes nothing, renders with the real Remotion composition, muxes audio and runs delivery QA. Two verified long-form fixtures are rendered in CI and uploaded as artifacts:

- `longform-acceptance` renders `projects/tsmc.generated.json`, a verified 3-minute-plus documentary built from `projects/evidence.tsmc.json` (TSMC corporate pages and its authoritative Wikipedia article, slotted into six narrative chapters). Tests pin the runtime window and re-validate the editorial gate on every push.
- `cables-acceptance` renders `projects/cables.generated.json`, a ~8-minute documentary built from `projects/evidence.cables.json`, a 57-item chaptered pack citing the live Wikipedia "Submarine communications cable" article. Tests pin it to a 5–8 minute window, enforce the verified single-source URL, and re-validate the editorial gate.

Every render runs three QA layers that must all pass for the build to succeed: **editorial** (readability density, visual-run variety, near-duplicate detection, chapter rhythm), **frame** (one-per-second `signalstats` luma sampling rejects a void or underfilled picture without false-flagging the deliberately dark documentary aesthetic), and **delivery** (ffprobe container/stream integrity).

```bash
npm run test        # full Python suite (128 tests, incl. fixture + frame QA guards)
npm run typecheck   # Remotion/TypeScript layer
npm run python-check
```

On-device verification: `tests/test_local_espeak.py` synthesizes real narration through any local espeak binary over stdin, retimes the beats, assembles the narration master with FFmpeg and writes editorial QA + manifest — it runs on-device (Termux) and skips itself where no espeak binary exists.

## Licensing

FLVYT's original code is provided separately from third-party components. Check `vendor/upstream.lock.json` and `LICENSES/` before redistributing a build. Remotion has a special license; verify its current terms for your organization before commercial redistribution of the software itself. Optional research/TTS/model packages and individual voice models retain their own licenses.
