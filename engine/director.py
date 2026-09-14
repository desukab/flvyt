from __future__ import annotations

from .project import Beat, Project
from .editorial import add_shots

# Documentary editing grammar. Deterministic by design: the same script produces
# a repeatable visual plan, making automated rendering debuggable.
VISUALS = {
    "claim": ("text", 3.2),
    "stat": ("counter", 2.8),
    "person": ("portrait", 3.5),
    "company": ("logo", 3.0),
    "map": ("map", 4.0),
    "timeline": ("timeline", 4.0),
    "quote": ("quote", 3.4),
    "title": ("title", 4.0),
    "broll": ("broll", 4.0),
}


def direct(project: Project) -> Project:
    """Normalize beats into an executable visual plan owned by FLVYT."""
    planned: list[Beat] = []
    for i, beat in enumerate(project.beats or []):
        visual, default_seconds = VISUALS.get(beat.visual, VISUALS["claim"])
        seconds = beat.seconds if beat.seconds > 0 else default_seconds
        if beat.emphasis == "high":
            seconds = max(1.8, seconds - 0.35)
        planned.append(Beat(
            id=beat.id or f"beat_{i+1:03d}", kind=beat.kind, text=beat.text,
            seconds=seconds, visual=visual, emphasis=beat.emphasis,
            assetSrc=beat.assetSrc, label=beat.label, value=beat.value,
            unit=beat.unit, narration=beat.narration, sources=list(beat.sources),
            shots=list(beat.shots),
        ))
    add_shots(planned)
    return Project(project.title, project.subtitle, project.fps, project.width, project.height, planned)
