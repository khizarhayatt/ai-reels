"""ElevenLabs TTS voiceover agent — generates one MP3 per scene."""

from __future__ import annotations

import time
from pathlib import Path

import requests

from config import Settings
from models.video_plan import VideoPlan

_ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Delay between TTS requests to avoid rate limits
_REQUEST_DELAY = 0.5


# ── Public API ────────────────────────────────────────────────────────────────

def generate_voiceovers_for_plan(
    plan: VideoPlan,
    output_dir: Path,
    settings: Settings,
) -> VideoPlan:
    """Generate voiceover MP3s for every scene. Returns the mutated plan."""
    lang_code = _language_to_code(plan.language)

    for scene in plan.scenes:
        scene_dir = output_dir / f"scene_{scene.scene_number:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        dest = scene_dir / "voiceover.mp3"

        audio_bytes = _generate_tts(
            text=scene.voiceover_text,
            settings=settings,
            language_code=lang_code,
        )
        if audio_bytes:
            dest.write_bytes(audio_bytes)
            scene.voiceover_audio_path = str(dest)

        time.sleep(_REQUEST_DELAY)

    return plan


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_tts(
    text: str,
    settings: Settings,
    language_code: str = "en",
) -> bytes | None:
    """Call the ElevenLabs REST API and return raw MP3 bytes."""
    url = _ELEVENLABS_TTS_URL.format(voice_id=settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
        "language_code": language_code,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.content
    except requests.HTTPError as exc:
        # Non-fatal: log and continue without voiceover for this scene
        import warnings
        warnings.warn(f"ElevenLabs TTS failed for scene: {exc}", stacklevel=2)
        return None
    except requests.RequestException as exc:
        import warnings
        warnings.warn(f"ElevenLabs request error: {exc}", stacklevel=2)
        return None


def _language_to_code(language: str) -> str:
    """Map a human-readable language name or code to an ISO 639-1 code."""
    mapping = {
        "english": "en", "en": "en",
        "spanish": "es", "es": "es",
        "french": "fr", "fr": "fr",
        "german": "de", "de": "de",
        "portuguese": "pt", "pt": "pt",
        "italian": "it", "it": "it",
        "dutch": "nl", "nl": "nl",
        "polish": "pl", "pl": "pl",
        "arabic": "ar", "ar": "ar",
        "hindi": "hi", "hi": "hi",
        "japanese": "ja", "ja": "ja",
        "korean": "ko", "ko": "ko",
        "chinese": "zh", "zh": "zh",
    }
    return mapping.get(language.lower(), "en")
