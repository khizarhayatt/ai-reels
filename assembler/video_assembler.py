"""MoviePy video assembler — combines Pexels clips, voiceover audio, and text overlays."""

from __future__ import annotations

from pathlib import Path

from models.video_plan import Scene, VideoPlan


def assemble_video(plan: VideoPlan, output_dir: Path) -> Path:
    """Assemble the final MP4 from scene clips, voiceovers, and on-screen text.

    Returns the path to the assembled video file.

    Requires: moviepy, pillow, imageio[ffmpeg]
    """
    try:
        from moviepy.editor import (
            AudioFileClip,
            CompositeVideoClip,
            ImageClip,
            TextClip,
            VideoFileClip,
            concatenate_videoclips,
        )
    except ImportError as exc:
        raise AssemblerError(
            "moviepy is required for video assembly. "
            "Run: pip install moviepy imageio[ffmpeg]"
        ) from exc

    scene_clips = []

    for scene in plan.scenes:
        clip = _build_scene_clip(scene, plan.platform, VideoFileClip, ImageClip)

        # Trim or loop to match the scene's target duration
        target = scene.duration_seconds
        if clip.duration > target:
            clip = clip.subclip(0, target)
        elif clip.duration < target:
            # Loop the clip to fill duration
            loops = int(target / clip.duration) + 1
            from moviepy.editor import concatenate_videoclips as _concat
            clip = _concat([clip] * loops).subclip(0, target)

        # Attach voiceover audio
        if scene.voiceover_audio_path and Path(scene.voiceover_audio_path).exists():
            audio = AudioFileClip(scene.voiceover_audio_path)
            audio = audio.subclip(0, min(audio.duration, clip.duration))
            clip = clip.set_audio(audio)

        # Add on-screen text overlay
        if scene.on_screen_text:
            try:
                txt = (
                    TextClip(
                        scene.on_screen_text,
                        fontsize=48,
                        color="white",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(clip.w, None),
                    )
                    .set_duration(clip.duration)
                    .set_position(("center", "bottom"))
                )
                clip = CompositeVideoClip([clip, txt])
            except Exception:
                pass  # Text overlay is best-effort

        # Apply fade transition
        if scene.transition == "fade":
            clip = clip.fadein(0.3).fadeout(0.3)

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

def _build_scene_clip(scene: Scene, platform: str, VideoFileClip, ImageClip):
    """Build a raw clip (no audio/text yet) from the first downloaded visual."""
    # Use first available visual with a local_path
    for visual in scene.visuals:
        path = getattr(visual, "local_path", None)
        if path and Path(path).exists():
            if path.endswith(".mp4"):
                return VideoFileClip(path)
            else:
                return ImageClip(path).set_duration(scene.duration_seconds)

    # Fallback: black frame clip
    return _black_clip(scene.duration_seconds, platform)


def _black_clip(duration: float, platform: str):
    """Create a plain black video clip as a fallback."""
    from moviepy.editor import ColorClip
    size = (1080, 1920) if platform in ("reels", "shorts", "tiktok") else (1920, 1080)
    return ColorClip(size=size, color=(0, 0, 0), duration=duration)


class AssemblerError(RuntimeError):
    """Raised when video assembly fails."""
