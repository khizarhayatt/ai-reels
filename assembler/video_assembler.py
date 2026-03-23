"""MoviePy 2.x video assembler — combines Pexels clips, voiceover audio, and text overlays."""

from __future__ import annotations

from pathlib import Path

from models.video_plan import Scene, VideoPlan


def assemble_video(plan: VideoPlan, output_dir: Path) -> Path:
    """Assemble the final MP4 from scene clips, voiceovers, and on-screen text.

    Compatible with MoviePy 2.x API.
    """
    try:
        from moviepy import (
            AudioFileClip,
            ColorClip,
            CompositeVideoClip,
            ImageClip,
            TextClip,
            VideoFileClip,
            concatenate_videoclips,
        )
        import moviepy.video.fx as vfx
    except ImportError as exc:
        raise AssemblerError(
            "moviepy is required for video assembly. "
            "Run: pip install moviepy imageio[ffmpeg]"
        ) from exc

    scene_clips = []

    for scene in plan.scenes:
        target = scene.duration_seconds

        # ── Build base clip from visual ───────────────────────────────
        clip = _build_scene_clip(scene, plan.platform, VideoFileClip, ImageClip, ColorClip)

        # Trim or loop to match target duration
        if clip.duration > target:
            clip = clip.subclipped(0, target)
        elif clip.duration < target:
            loops = int(target / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops).subclipped(0, target)

        # ── Attach voiceover audio ────────────────────────────────────
        if scene.voiceover_audio_path and Path(scene.voiceover_audio_path).exists():
            audio = AudioFileClip(scene.voiceover_audio_path)
            audio = audio.subclipped(0, min(audio.duration, clip.duration))
            clip = clip.with_audio(audio)

        # ── Add on-screen text overlay ────────────────────────────────
        if scene.on_screen_text:
            try:
                txt = (
                    TextClip(
                        text=scene.on_screen_text,
                        font_size=48,
                        color="white",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(clip.w, None),
                    )
                    .with_duration(clip.duration)
                    .with_position(("center", "bottom"))
                )
                clip = CompositeVideoClip([clip, txt])
            except Exception:
                pass  # Text overlay is best-effort

        # ── Apply fade transition ─────────────────────────────────────
        if scene.transition == "fade":
            clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])

        scene_clips.append(clip)

    if not scene_clips:
        raise AssemblerError("No scene clips could be built — check that visuals were downloaded.")

    final = concatenate_videoclips(scene_clips, method="compose")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "final_video.mp4"

    final.write_videofile(
        str(out_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(output_dir / "temp_audio.m4a"),
        remove_temp=True,
        logger=None,
    )

    return out_path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_scene_clip(scene: Scene, platform: str, VideoFileClip, ImageClip, ColorClip):
    """Return a raw clip from the first downloaded visual for this scene."""
    for visual in scene.visuals:
        path = getattr(visual, "local_path", None)
        if path and Path(path).exists():
            if path.endswith(".mp4"):
                return VideoFileClip(path)
            else:
                return ImageClip(path).with_duration(scene.duration_seconds)

    # Fallback: black frame
    return _black_clip(scene.duration_seconds, platform, ColorClip)


def _black_clip(duration: float, platform: str, ColorClip):
    size = (1080, 1920) if platform in ("reels", "shorts", "tiktok") else (1920, 1080)
    return ColorClip(size=size, color=(0, 0, 0)).with_duration(duration)


class AssemblerError(RuntimeError):
    """Raised when video assembly fails."""
