# FLVYT

Automated faceless technology-documentary production engine.

## The idea

FLVYT is **not another video editor written from scratch**. It is the editorial brain and orchestration layer sitting on top of proven video infrastructure.

```text
Topic / research / evidence
        ↓
Script + documentary beats
        ↓
Editorial director
        ↓
Visual plan + asset registry
        ↓
Local narration (optional) + local transcription
        ↓
Remotion motion graphics / B-roll treatment
        ↓
FFmpeg audio mix + delivery mux
        ↓
QA gates
        ↓
Final MP4
```

The target is a serious faceless technology channel: controlled pacing, visual hierarchy, charts/maps/timelines, documentary typography and repeatable motion — without manually editing every shot.

## Reused infrastructure

- **video-autopilot-kit** — MIT-licensed reusable production gates, media helpers, audio chain, captions and QA. Run `python scripts/bootstrap_upstream.py` to vendor the selected modules locally.
- **Remotion 4.0.524** — programmatic React video rendering and motion graphics.
- **FFmpeg** — local audio/video processing and delivery.
- **faster-whisper (optional)** — local word/segment timestamps. No cloud transcription is required.

The upstream MIT notice is preserved in `LICENSES/VIDEO_AUTOPILOT_KIT_MIT.txt` and copied into the vendor directory by the bootstrap script.

## Quick start

Requirements: Node 20+, Python 3.10+, FFmpeg.

```bash
npm install
python scripts/bootstrap_upstream.py
python -m compileall engine scripts
npm run typecheck
python scripts/render.py projects/demo.json --out out/demo.mp4
```

The renderer is deterministic: the JSON project is normalized by `engine/director.py`, converted to Remotion props, rendered without a manual timeline, then given an audio stream and delivery QA.

## Local narration

FLVYT does not hard-code a paid TTS API. Install any local TTS executable you are licensed to use and pass its command template to the adapter. For example, a local Piper installation can be wired as:

```bash
python scripts/synthesize.py projects/demo.json \
  --command 'piper --model {model} --output_file {output}' \
  --model /path/to/voice.onnx

python scripts/render.py projects/demo.json --out out/demo.mp4
```

The TTS manifest is then concatenated in beat order. If no narration exists, the demo still renders with a valid silent audio track.

## Local transcription + captions

```bash
python -m pip install -r requirements-local.txt
python scripts/transcribe.py input.wav --model small --output out/transcript.json
python scripts/render.py projects/demo.json --transcript out/transcript.json --out out/final.mp4
```

The transcript contains word timestamps; the renderer can convert them into an SRT subtitle stream and mux it into the MP4.

## Asset discipline

`engine/assets.py` provides a registry that requires every selected asset to carry an explicit ownership/license class such as `owned`, `public-domain`, `cc0`, `cc-by`, `cc-by-sa`, or `licensed`. FLVYT does not automatically scrape arbitrary copyrighted B-roll.

## Development

```bash
npm run typecheck
npm run python-check
npm run start
```

## Architecture boundary

FLVYT owns the **editorial intelligence**: beat planning, visual intent, timing, asset matching, reusable motion primitives and deterministic orchestration. Remotion owns programmatic visuals; FFmpeg/upstream tooling owns media processing, audio, captions and delivery gates.

## Licensing

FLVYT's original code is provided separately from third-party components. Check `vendor/upstream.lock.json` and `LICENSES/` before redistributing a build. Remotion has a special license; its current Free License covers individuals and for-profit organizations with up to 3 employees for commercial video creation, while larger for-profit organizations may require a Company License.
