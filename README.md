# FLVYT

Production-oriented automated faceless technology-documentary engine.

## What this is

FLVYT is **not another video editor written from scratch**. It is the editorial brain and orchestration layer sitting on top of proven video infrastructure.

```text
Topic / research / evidence
        ↓
Grounded story + documentary beats
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
- **Piper or another locally installed TTS engine** — local narration with no paid API requirement.

The upstream MIT notice is preserved in `LICENSES/VIDEO_AUTOPILOT_KIT_MIT.txt` and copied into the vendor directory by the bootstrap script.

## One-command production build

Requirements: Node 20+, Python 3.10+, FFmpeg. For narration/captions, install the optional local dependencies and a local TTS voice.

```bash
npm install
python scripts/bootstrap_upstream.py
python -m compileall engine scripts
npm run typecheck
```

With a ready evidence pack:

```bash
python scripts/build.py projects/evidence.example.json \
  --tts-command 'piper --model {model} --output_file {output}' \
  --tts-model /path/to/voice.onnx \
  --out out/final.mp4
```

Without narration, the same pipeline renders a valid video with a silent audio track:

```bash
python scripts/build.py projects/evidence.example.json --out out/final.mp4
```

The build performs story planning, asset matching when a registry is supplied, TTS synthesis, narration-driven beat timing, local transcription, captions, Remotion rendering, FFmpeg audio processing and delivery QA.

## Evidence format

The preferred production input is an evidence pack. It keeps claims tied to sources rather than asking the renderer to invent facts.

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

FLVYT does not require a paid TTS provider. The TTS adapter accepts any local executable using `{model}` and `{output}` placeholders. Piper is one supported option. Review the license of the specific voice model before commercial use; the Piper software is MIT, while individual voice models can have their own licensing terms. citeturn0search0turn0search1

After synthesis, FLVYT measures each narration clip and retimes the corresponding visual beat. This prevents the common automated-video failure where narration and visuals drift apart.

## Captions

Install the local transcription dependency:

```bash
python -m pip install -r requirements-local.txt
```

When TTS is enabled, `scripts/build.py` automatically transcribes the assembled narration with faster-whisper and muxes timed SRT captions into the MP4. Caption timestamps account for the documentary intro.

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

FLVYT owns the **editorial intelligence**: beat planning, visual intent, timing, asset matching, reusable motion primitives and deterministic orchestration. Remotion owns programmatic visuals; FFmpeg and the reused upstream tooling own media processing, audio, captions and delivery gates.

## Validation

GitHub Actions validates both the Python layer and the Remotion/TypeScript layer on every push.

```bash
npm run typecheck
npm run python-check
```

## Licensing

FLVYT's original code is provided separately from third-party components. Check `vendor/upstream.lock.json` and `LICENSES/` before redistributing a build. Remotion has a special license; verify its current terms for your organization before commercial redistribution of the software itself.
