"""Central configuration — loads .env and exposes Settings + PLATFORM_CONFIGS."""

from __future__ import annotations

import os
from dataclasses import dataclass

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
    # API keys
    openai_api_key: str
    pexels_api_key: str
    google_tts_api_key: str

    # OpenAI
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096

    # Google TTS
    google_tts_language_code: str = "en-US"
    google_tts_voice_name: str = "en-US-Neural2-F"
    google_tts_audio_encoding: str = "MP3"
    google_tts_speaking_rate: float = 1.1
    google_tts_pitch: float = 0.0

    # Pexels
    pexels_per_page: int = 5
    pexels_video_min_duration: int = 3
    pexels_video_max_duration: int = 15

    # Output
    output_dir: str = "output"


def load_settings() -> Settings:
    """Load settings from environment. Raises EnvironmentError for missing required keys."""
    missing = [k for k in ("OPENAI_API_KEY", "PEXELS_API_KEY", "GOOGLE_TTS_API_KEY")
               if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your API keys."
        )

    return Settings(
        openai_api_key=os.environ["OPENAI_API_KEY"],
        pexels_api_key=os.environ["PEXELS_API_KEY"],
        google_tts_api_key=os.environ["GOOGLE_TTS_API_KEY"],
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        openai_max_tokens=int(os.environ.get("OPENAI_MAX_TOKENS", "4096")),
        google_tts_language_code=os.environ.get("GOOGLE_TTS_LANGUAGE_CODE", "en-US"),
        google_tts_voice_name=os.environ.get("GOOGLE_TTS_VOICE_NAME", "en-US-Neural2-F"),
        google_tts_audio_encoding=os.environ.get("GOOGLE_TTS_AUDIO_ENCODING", "MP3"),
        google_tts_speaking_rate=float(os.environ.get("GOOGLE_TTS_SPEAKING_RATE", "1.1")),
        google_tts_pitch=float(os.environ.get("GOOGLE_TTS_PITCH", "0.0")),
        pexels_per_page=int(os.environ.get("PEXELS_PER_PAGE", "5")),
        pexels_video_min_duration=int(os.environ.get("PEXELS_VIDEO_MIN_DURATION", "3")),
        pexels_video_max_duration=int(os.environ.get("PEXELS_VIDEO_MAX_DURATION", "15")),
        output_dir=os.environ.get("OUTPUT_DIR", "output"),
    )
