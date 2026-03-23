#!/usr/bin/env python3
"""AI Reels — Video Automation Agent CLI.

Usage:
    python main.py generate \\
        --topic "5 habits that destroy productivity" \\
        --platform reels \\
        --tone educational \\
        --duration 60 \\
        --language en

    # With full video assembly:
    python main.py generate --topic "Morning routines" --platform shorts \\
        --tone motivational --duration 30 --language en --assemble

    # Skip API calls (plan only):
    python main.py generate --topic "AI trends 2025" --platform youtube \\
        --tone educational --duration 300 --language en \\
        --no-visuals --no-voiceover
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import PLATFORM_CONFIGS, load_settings

console = Console()


@click.group()
def cli() -> None:
    """AI Reels — Viral Video Automation Agent."""


@cli.command()
@click.option("--topic",    required=True,  help="Video topic or idea.")
@click.option("--platform", required=True,
              type=click.Choice(["reels", "shorts", "tiktok", "youtube"], case_sensitive=False),
              help="Target platform.")
@click.option("--tone",     required=True,
              type=click.Choice(
                  ["educational", "entertaining", "motivational",
                   "storytelling", "inspirational", "humorous", "professional"],
                  case_sensitive=False),
              help="Video tone / style.")
@click.option("--duration", required=True, type=int,
              help="Target duration in seconds (e.g. 30, 60, 300).")
@click.option("--language", default="en", show_default=True,
              help="Language for voiceover and script (e.g. en, es, fr).")
@click.option("--assemble", is_flag=True, default=False,
              help="Assemble the final MP4 using MoviePy.")
@click.option("--no-visuals",  "skip_visuals",   is_flag=True, default=False,
              help="Skip Pexels visual downloads.")
@click.option("--no-voiceover", "skip_voiceover", is_flag=True, default=False,
              help="Skip ElevenLabs voiceover generation.")
@click.option("--output-dir", default=None,
              help="Override output directory (default: output/<slug>).")
def generate(
    topic: str,
    platform: str,
    tone: str,
    duration: int,
    language: str,
    assemble: bool,
    skip_visuals: bool,
    skip_voiceover: bool,
    output_dir: str | None,
) -> None:
    """Generate a full viral video plan (and optionally assemble the video)."""

    # ── Validate platform duration ────────────────────────────────────────
    cfg = PLATFORM_CONFIGS[platform]
    if duration > cfg.max_duration:
        console.print(
            f"[yellow]Warning:[/] {platform} max duration is {cfg.max_duration}s "
            f"but you requested {duration}s. Capping at {cfg.max_duration}s."
        )
        duration = cfg.max_duration

    # ── Load settings (validates API keys) ───────────────────────────────
    try:
        settings = load_settings()
    except EnvironmentError as exc:
        console.print(f"[red]Configuration error:[/] {exc}")
        sys.exit(1)

    # ── Determine output directory ────────────────────────────────────────
    slug = _make_slug(topic)
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out  = Path(output_dir) if output_dir else Path(settings.output_dir) / f"{slug}_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold cyan]AI Reels[/] — Video Automation Agent\n"
        f"Topic: [bold]{topic}[/]  |  Platform: [bold]{platform}[/]  |  "
        f"Tone: [bold]{tone}[/]  |  Duration: [bold]{duration}s[/]  |  "
        f"Language: [bold]{language}[/]",
        border_style="cyan",
    ))

    # ── Step 1: Generate script via Claude ────────────────────────────────
    console.print("\n[bold]Step 1/4[/] Generating script with Claude AI…")
    from agents.script_agent import ScriptGenerationError, generate_video_plan
    try:
        plan = generate_video_plan(topic, platform, tone, duration, language, settings)
    except ScriptGenerationError as exc:
        console.print(f"[red]Script generation failed:[/] {exc}")
        sys.exit(1)

    plan.output_slug = f"{slug}_{ts}"
    console.print(f"  [green]✓[/] {len(plan.scenes)} scenes generated")
    console.print(f"  [green]✓[/] Viral hook: [italic]{plan.viral_hook[:80]}…[/]")

    # ── Step 2: Fetch Pexels visuals ──────────────────────────────────────
    if not skip_visuals:
        console.print("\n[bold]Step 2/4[/] Fetching Pexels visuals…")
        from agents.visual_agent import fetch_visuals_for_plan
        plan = fetch_visuals_for_plan(plan, out, settings)
        downloaded = sum(len(s.visuals) for s in plan.scenes)
        console.print(f"  [green]✓[/] {downloaded} visual assets downloaded")
    else:
        console.print("\n[bold]Step 2/4[/] [dim]Skipping visuals (--no-visuals)[/]")

    # ── Step 3: Generate voiceovers via ElevenLabs ────────────────────────
    if not skip_voiceover:
        console.print("\n[bold]Step 3/4[/] Generating voiceovers with ElevenLabs…")
        from agents.voiceover_agent import generate_voiceovers_for_plan
        plan = generate_voiceovers_for_plan(plan, out, settings)
        with_audio = sum(1 for s in plan.scenes if s.voiceover_audio_path)
        console.print(f"  [green]✓[/] {with_audio}/{len(plan.scenes)} voiceovers generated")
    else:
        console.print("\n[bold]Step 3/4[/] [dim]Skipping voiceover (--no-voiceover)[/]")

    # ── Step 4: Export plan JSON ──────────────────────────────────────────
    console.print("\n[bold]Step 4/4[/] Exporting plan…")
    from exporters.json_exporter import export_plan
    from exporters.youtube_exporter import export_youtube_metadata

    plan_path = export_plan(plan, out)
    plan.json_plan_path = str(plan_path)
    console.print(f"  [green]✓[/] Plan saved → {plan_path}")

    yt_path = export_youtube_metadata(plan, out)
    if yt_path:
        console.print(f"  [green]✓[/] YouTube metadata → {yt_path}")

    # ── Optional: Assemble final video ────────────────────────────────────
    if assemble:
        console.print("\n[bold]Assembling final video (MoviePy)…[/]")
        from assembler.video_assembler import AssemblerError, assemble_video
        try:
            video_path = assemble_video(plan, out)
            plan.final_video_path = str(video_path)
            console.print(f"  [green]✓[/] Final video → {video_path}")
        except AssemblerError as exc:
            console.print(f"  [yellow]Assembly skipped:[/] {exc}")

    # ── Summary table ─────────────────────────────────────────────────────
    _print_summary(plan, out)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_slug(text: str) -> str:
    """Convert topic to a safe directory slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:40]


def _print_summary(plan, out: Path) -> None:
    console.print()

    # Scene table
    table = Table(title="Scene Breakdown", show_header=True, header_style="bold magenta")
    table.add_column("#",      style="dim", width=4)
    table.add_column("Voice",  max_width=40)
    table.add_column("Visual", max_width=25)
    table.add_column("Text",   max_width=20)
    table.add_column("Dur",    width=5)

    for s in plan.scenes:
        table.add_row(
            str(s.scene_number),
            s.voiceover_text[:60] + ("…" if len(s.voiceover_text) > 60 else ""),
            s.pexels_query,
            s.on_screen_text or "",
            f"{s.duration_seconds:.0f}s",
        )
    console.print(table)

    # Hashtags
    if plan.hashtags:
        console.print("\n[bold]Hashtags:[/] " + "  ".join(plan.hashtags[:15]))

    # Background music
    console.print(f"\n[bold]Music:[/] {plan.background_music_suggestion}")

    # Voiceover instructions
    vi = plan.voiceover_instructions
    console.print(f"[bold]Voice:[/] {vi.pace} — {vi.tone_description}")

    # YouTube metadata preview
    if plan.youtube_metadata:
        yt = plan.youtube_metadata
        console.print(Panel(
            f"[bold]Title:[/] {yt.title}\n"
            f"[bold]Category:[/] {yt.category}\n"
            f"[bold]Thumbnail:[/] {yt.thumbnail_concept}\n"
            f"[bold]CTA:[/] {yt.end_screen_cta}\n"
            f"[bold]Tags:[/] {', '.join(yt.tags[:8])}…",
            title="YouTube Metadata",
            border_style="blue",
        ))

    console.print(f"\n[bold green]Done![/] Output directory: [cyan]{out}[/]")


if __name__ == "__main__":
    cli()
