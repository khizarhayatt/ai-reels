"""OpenAI GPT-powered script generation agent.

Calls the OpenAI Chat Completions API and returns a fully-populated VideoPlan.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import openai

from config import PLATFORM_CONFIGS, Settings
from models.video_plan import Scene, VideoPlan, VoiceoverInstructions, YouTubeMetadata


# ── Prompt templates ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert viral content creator and professional scriptwriter specialising in \
{platform} content. You understand what makes videos go viral: pattern interrupts, \
emotional hooks, storytelling arcs, and platform-specific best practices.

You MUST respond with a single valid JSON object matching this exact schema — \
do NOT wrap it in markdown code fences:

{{
  "viral_hook": "<string: 0-3 sec opener that stops scrolling>",
  "full_script": "<string: complete narration, all scenes concatenated>",
  "scenes": [
    {{
      "scene_number": <int>,
      "duration_seconds": <float>,
      "voiceover_text": "<string>",
      "pexels_query": "<string: 2-5 word English B-roll search query>",
      "on_screen_text": "<string or null>",
      "transition": "cut|fade|zoom"
    }}
  ],
  "voiceover_instructions": {{
    "pace": "<string>",
    "tone_description": "<string>",
    "emphasis_words": ["<word>"],
    "pause_after_hook": <float seconds>
  }},
  "background_music_suggestion": "<string>",
  "hashtags": ["#tag1", "#tag2"],
  "youtube_metadata": null
}}

STRICT RULES:
- Total scene duration_seconds MUST sum to approximately {duration} seconds (±10%)
- Generate exactly {num_scenes} scenes
- pexels_query values MUST be in English regardless of the output language
- viral_hook must be the first sentence of full_script
- hashtags: exactly 12 tags mixing broad reach and niche topic
- For YouTube platform only: set youtube_metadata with title (max 60 chars), \
description (with keywords), tags list, category, thumbnail_concept, \
end_screen_cta, and chapters (every 60-90 seconds). Otherwise keep null.
- Sentences under 10 words; add pattern interrupts every 3-5 seconds
"""

_USER_PROMPT = """\
Create a {tone} {platform} video about: {topic}

Requirements:
- Language: {language}
- Duration: {duration} seconds
- Platform: {platform} ({aspect_ratio}, max {max_duration}s)
- Tone: {tone}
- Number of scenes: {num_scenes}

The viral hook must be provocative and create immediate curiosity or shock.
Every 5 seconds must introduce new value or a pattern interrupt.
Each pexels_query should be specific enough to find relevant B-roll footage.
"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_video_plan(
    topic: str,
    platform: str,
    tone: str,
    duration: int,
    language: str,
    settings: Settings,
) -> VideoPlan:
    """Generate a full VideoPlan using OpenAI GPT.

    Raises:
        ScriptGenerationError: on API failure or unrecoverable JSON parse error.
    """
    platform_cfg = PLATFORM_CONFIGS.get(platform)
    if platform_cfg is None:
        raise ValueError(f"Unknown platform '{platform}'. Choose from: {list(PLATFORM_CONFIGS)}")

    num_scenes = _calculate_num_scenes(platform, duration)
    system = _build_system_prompt(platform, duration, num_scenes)
    user = _build_user_prompt(topic, platform, tone, duration, language, num_scenes, platform_cfg)

    client = openai.OpenAI(api_key=settings.openai_api_key)
    raw_json = _call_openai_with_retry(client, system, user, settings)

    plan = _parse_response(raw_json, topic, platform, tone, duration, language)
    plan.created_at = datetime.now(timezone.utc).isoformat()
    return plan


# ── Internal helpers ──────────────────────────────────────────────────────────

def _calculate_num_scenes(platform: str, duration: int) -> int:
    """~5-8 seconds per scene for short-form; ~45 seconds per scene for YouTube."""
    if platform == "youtube":
        scenes = max(3, duration // 45)
    else:
        scenes = max(3, duration // 6)
    return min(scenes, PLATFORM_CONFIGS[platform].max_scenes)


def _build_system_prompt(platform: str, duration: int, num_scenes: int) -> str:
    return _SYSTEM_PROMPT.format(
        platform=platform,
        duration=duration,
        num_scenes=num_scenes,
    )


def _build_user_prompt(
    topic: str,
    platform: str,
    tone: str,
    duration: int,
    language: str,
    num_scenes: int,
    platform_cfg,
) -> str:
    return _USER_PROMPT.format(
        topic=topic,
        platform=platform,
        tone=tone,
        duration=duration,
        language=language,
        num_scenes=num_scenes,
        aspect_ratio=platform_cfg.aspect_ratio,
        max_duration=platform_cfg.max_duration,
    )


def _call_openai_with_retry(
    client: openai.OpenAI,
    system: str,
    user: str,
    settings: Settings,
    max_retries: int = 3,
) -> str:
    delay = 2
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=settings.openai_max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            return response.choices[0].message.content or ""
        except openai.RateLimitError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
        except openai.APIError as exc:
            raise ScriptGenerationError(f"OpenAI API error: {exc}") from exc

    raise ScriptGenerationError(f"Rate limit exceeded after {max_retries} retries: {last_error}")


def _parse_response(
    raw: str,
    topic: str,
    platform: str,
    tone: str,
    duration: int,
    language: str,
) -> VideoPlan:
    # Strip accidental markdown code fences (safety net, response_format should prevent this)
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScriptGenerationError(
            f"GPT returned invalid JSON: {exc}\n\nRaw output:\n{raw[:500]}"
        ) from exc

    # Inject input fields
    data["topic"] = topic
    data["platform"] = platform
    data["tone"] = tone
    data["duration_seconds"] = duration
    data["language"] = language

    # Coerce nested dicts → Pydantic models
    if isinstance(data.get("voiceover_instructions"), dict):
        data["voiceover_instructions"] = VoiceoverInstructions(**data["voiceover_instructions"])
    if isinstance(data.get("youtube_metadata"), dict):
        data["youtube_metadata"] = YouTubeMetadata(**data["youtube_metadata"])
    if isinstance(data.get("scenes"), list):
        data["scenes"] = [Scene(**s) if isinstance(s, dict) else s for s in data["scenes"]]

    try:
        plan = VideoPlan.model_validate(data)
    except Exception as exc:
        raise ScriptGenerationError(f"VideoPlan validation failed: {exc}") from exc

    # Warn if total duration drifts > 20%
    total = sum(s.duration_seconds for s in plan.scenes)
    if abs(total - duration) > duration * 0.20:
        import warnings
        warnings.warn(
            f"Scene durations sum to {total:.1f}s but target is {duration}s",
            stacklevel=2,
        )

    return plan


class ScriptGenerationError(RuntimeError):
    """Raised when script generation or parsing fails."""
