"""Pydantic data models — the single source of truth flowing through the pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class Platform(str, Enum):
    REELS = "reels"
    SHORTS = "shorts"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class Tone(str, Enum):
    EDUCATIONAL = "educational"
    ENTERTAINING = "entertaining"
    MOTIVATIONAL = "motivational"
    STORYTELLING = "storytelling"
    INSPIRATIONAL = "inspirational"
    CONTROVERSIAL = "controversial"
    HUMOROUS = "humorous"
    PROFESSIONAL = "professional"


class Transition(str, Enum):
    CUT = "cut"
    FADE = "fade"
    ZOOM = "zoom"


class PexelsVideo(BaseModel):
    video_id: int
    url: str
    duration: int
    width: int
    height: int
    download_url: str
    local_path: Optional[str] = None  # set after download


class PexelsImage(BaseModel):
    image_id: int
    url: str
    photographer: str
    download_url: str
    local_path: Optional[str] = None  # set after download


class Scene(BaseModel):
    scene_number: int
    duration_seconds: float
    voiceover_text: str
    pexels_query: str  # English search query for Pexels
    on_screen_text: Optional[str] = None
    transition: str = "fade"
    visuals: list[Union[PexelsVideo, PexelsImage]] = Field(default_factory=list)
    voiceover_audio_path: Optional[str] = None


class VoiceoverInstructions(BaseModel):
    pace: str
    tone_description: str
    emphasis_words: list[str] = Field(default_factory=list)
    pause_after_hook: float = 0.5  # seconds


class YouTubeMetadata(BaseModel):
    title: str  # SEO-optimised, max 100 chars
    description: str  # max 5000 chars
    tags: list[str]
    category: str = "Education"
    thumbnail_concept: str
    end_screen_cta: str
    chapters: list[dict] = Field(default_factory=list)  # [{title, start_seconds}]


class VideoPlan(BaseModel):
    # ── Input params (echoed for reproducibility) ──────────────────────────
    topic: str
    platform: str
    tone: str
    duration_seconds: int
    language: str

    # ── Generated content ──────────────────────────────────────────────────
    viral_hook: str
    full_script: str
    scenes: list[Scene]
    voiceover_instructions: VoiceoverInstructions
    background_music_suggestion: str
    hashtags: list[str] = Field(default_factory=list)
    youtube_metadata: Optional[YouTubeMetadata] = None

    # ── Runtime artifacts (set during pipeline execution) ──────────────────
    output_slug: str = ""
    json_plan_path: Optional[str] = None
    final_video_path: Optional[str] = None
    created_at: str = ""
