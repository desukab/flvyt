from __future__ import annotations

from .project import Beat, Project
from .editorial import add_shots
from .transitions import assign_transitions
from .story import read_need

# Documentary editing grammar. Deterministic by design: the same script produces
# a repeatable visual plan, making automated rendering debuggable.
VISUALS = {
    "claim": ("text", 3.2),
    "stat": ("counter", 2.8),
    "chart": ("chart", 4.0),
    "person": ("portrait", 3.5),
    "portrait": ("portrait", 3.5),
    "company": ("logo", 3.0),
    "logo": ("logo", 3.0),
    "map": ("map", 4.0),
    "timeline": ("timeline", 4.0),
    "quote": ("quote", 3.4),
    "title": ("title", 4.0),
    "broll": ("broll", 4.0),
    "chapter": ("chapter", 3.5),
}


def direct(project: Project) -> Project:
    """Normalize beats into an executable visual plan owned by FLVYT.

    Beat seconds are the single source of truth: the renderer must not silently
    shorten what the editorial plan advertised, or the planned runtime stops
    matching the delivered video.

    A beat authored with a too-short duration is lengthened to the readability
    floor — *unless* the project is timed by audio. Once narration exists, the
    actual TTS duration is the truth: re-flooring to a reading-rate estimate
    would stretch the picture beyond the voice and leave a silent tail.
    """
    planned: list[Beat] = []
    for i, beat in enumerate(project.beats or []):
        visual, default_seconds = VISUALS.get(beat.visual, VISUALS["claim"])
        seconds = beat.seconds if beat.seconds > 0 else default_seconds
        if not project.timed_by_audio:
            seconds = max(float(seconds), read_need(beat.text))
        planned.append(Beat(
            id=beat.id or f"beat_{i+1:03d}", kind=beat.kind, text=beat.text,
            seconds=seconds, visual=visual, emphasis=beat.emphasis,
            assetSrc=beat.assetSrc, assetConfidence=beat.assetConfidence,
            assetReason=beat.assetReason, label=beat.label, value=beat.value,
            unit=beat.unit, narration=beat.narration, sources=list(beat.sources),
            shots=list(beat.shots), pad_after=beat.pad_after,
            chapter=beat.chapter, intent=beat.intent, motif=beat.motif,
            tags=list(beat.tags) if beat.tags else None,
        ))
    add_shots(planned)
    assign_transitions(planned)
    return Project(project.title, project.subtitle, project.fps, project.width,
                   project.height, planned, timed_by_audio=project.timed_by_audio)
