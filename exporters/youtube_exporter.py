"""YouTube metadata exporter — writes youtube_metadata.json."""

from __future__ import annotations

import json
from pathlib import Path

from models.video_plan import VideoPlan


def export_youtube_metadata(plan: VideoPlan, output_dir: Path) -> Path | None:
    """Write youtube_metadata.json if the plan includes YouTube metadata.

    Returns the path to the written file, or None if not a YouTube plan.
    """
    if plan.youtube_metadata is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "youtube_metadata.json"

    meta = plan.youtube_metadata.model_dump(mode="json")
    # Enrich with top-level hashtags if present
    if plan.hashtags:
        meta["hashtags"] = plan.hashtags

    dest.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest
