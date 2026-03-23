"""Central configuration — loads .env and exposes Settings + PLATFORM_CONFIGS."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PlatformConfig:
    aspect_ratio: str
    max_duration: int  # seconds
    max_scenes: int
    orientation: str  # "portrait" | "landscape"


PLATFORM_CONFIGS: dict[str, PlatformConfig] = {
    "reels":   PlatformConfig("9:16", 90,  12, "portrait"),
    "shorts":  PlatformConfig("9:16", 60,  10, "portrait"),
    "tiktok":  PlatformConfig("9:16", 180, 18, "portrait"),
    "youtube": PlatformConfig("16:9", 600, 50, "landscape"),
}


@dataclass
class Settings:
    anthropic_api_key: str
    pexels_api_key: str
    elevenlabs_api_key: str
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 8192
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_128"
    pexels_per_page: int = 5
    pexels_video_min_duration: int = 3
    pexels_video_max_duration: int = 15
    output_dir: str = "output"


def load_settings() -> Settings:
    """Load settings from environment. Raises EnvironmentError for missing required keys."""
    missing = []
    required = ["ANTHROPIC_API_KEY", "PEXELS_API_KEY", "ELEVENLABS_API_KEY"]
    for key in required:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your API keys."
        )

    return Settings(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        pexels_api_key=os.environ["PEXELS_API_KEY"],
        elevenlabs_api_key=os.environ["ELEVENLABS_API_KEY"],
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        claude_max_tokens=int(os.environ.get("CLAUDE_MAX_TOKENS", "8192")),
        elevenlabs_voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        elevenlabs_model_id=os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        elevenlabs_output_format=os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
        pexels_per_page=int(os.environ.get("PEXELS_PER_PAGE", "5")),
        pexels_video_min_duration=int(os.environ.get("PEXELS_VIDEO_MIN_DURATION", "3")),
        pexels_video_max_duration=int(os.environ.get("PEXELS_VIDEO_MAX_DURATION", "15")),
        output_dir=os.environ.get("OUTPUT_DIR", "output"),
    )
