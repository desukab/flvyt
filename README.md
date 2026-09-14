# FLVYT

Automated faceless technology documentary video production engine.

## What this is

FLVYT is **not another video editor written from scratch**. It is the editorial brain and orchestration layer sitting on top of proven tooling.

```text
Project / research
      ↓
Editorial director
      ↓
Beat + visual plan
      ↓
Remotion motion graphics
      ↓
FFmpeg / upstream media tooling
      ↓
Audio + captions + QA
      ↓
Final documentary
```

## Reused infrastructure

- **video-autopilot-kit** — MIT-licensed reusable production gates, media helpers, audio chain, captions and QA. Run `python scripts/bootstrap_upstream.py` to vendor the selected modules locally.
- **Remotion 4.0.524** — programmatic React video rendering and motion graphics.
- **FFmpeg** — media processing and final delivery.

The upstream MIT notice is preserved in `LICENSES/VIDEO_AUTOPILOT_KIT_MIT.txt` and copied into the vendor directory by the bootstrap script.

## First working path

```bash
# 1. Install Node 20+, Python 3.10+, and FFmpeg
npm install

# 2. Pull the reusable upstream production components
python scripts/bootstrap_upstream.py

# 3. Render the included documentary test
python scripts/render.py projects/demo.json --out out/demo.mp4
```

The renderer is deterministic: the JSON project is normalized by `engine/director.py`, converted to Remotion props, and rendered without a manual timeline.

## Development

```bash
npm run typecheck
npm run start
```

The next integration layers are asset matching, local transcription/TTS adapters, real documentary scene components (maps, charts, timelines, evidence cards), and the upstream audio/caption/quality gates.

## Licensing

FLVYT's original code is provided separately from third-party components. Check `vendor/upstream.lock.json` and `LICENSES/` before redistributing a build. Remotion has a special license; its current Free License covers individuals and for-profit organizations with up to 3 employees for commercial video creation, while larger for-profit organizations may require a Company License.
