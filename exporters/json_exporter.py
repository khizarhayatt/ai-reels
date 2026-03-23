"""JSON exporter — serialises the full VideoPlan to plan.json."""

from __future__ import annotations

import json
from pathlib import Path

from models.video_plan import VideoPlan


def export_plan(plan: VideoPlan, output_dir: Path) -> Path:
    """Write plan.json to output_dir. Returns the path to the written file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "plan.json"
    data = plan.model_dump(mode="json")
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest
