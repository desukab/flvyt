from __future__ import annotations

from .project import Beat, Project

# Documentary editing grammar. These are intentionally deterministic: the same
# script produces the same plan, making automated rendering debuggable.
VISUALS = {
    "claim": ("text", 3.2),
    "stat": ("counter", 2.8),
    "person": ("portrait", 3.5),
    "company": ("logo", 3.0),
    "map": ("map", 4.0),
    "timeline": ("timeline", 4.0),
    "quote": ("quote", 3.4),
    "title": ("title", 4.0),
}


def direct(project: Project) -> Project:
    """Normalize beats into an executable visual plan.

    This is the part FLVYT owns. Rendering, audio processing, captions and
    quality gates are delegated to proven infrastructure rather than rebuilt.
    """
    planned: list[Beat] = []
    for i, beat in enumerate(project.beats or []):
        visual, default_seconds = VISUALS.get(beat.visual, VISUALS["claim"])
        seconds = beat.seconds if beat.seconds > 0 else default_seconds
        if beat.emphasis == "high":
            seconds = max(1.8, seconds - 0.35)
        planned.append(Beat(
            id=beat.id or f"beat_{i+1:03d}", kind=beat.kind, text=beat.text,
            seconds=seconds, visual=visual, emphasis=beat.emphasis,
        ))
    return Project(project.title, project.subtitle, project.fps, project.width, project.height, planned)
