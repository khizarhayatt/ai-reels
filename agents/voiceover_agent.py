"""Google Cloud Text-to-Speech voiceover agent — generates one MP3 per scene.

Uses the Google Cloud TTS REST API (v1) with an API key.
No service-account JSON required — just set GOOGLE_TTS_API_KEY in .env.

Docs: https://cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from config import Settings
from models.video_plan import VideoPlan

_GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Seconds to wait between requests to stay within free-tier quota
_REQUEST_DELAY = 0.3

# Maps ISO 639-1 / human name → BCP-47 language code used by Google TTS
_LANGUAGE_MAP: dict[str, str] = {
    "en": "en-US", "english": "en-US",
    "es": "es-ES", "spanish": "es-ES",
    "fr": "fr-FR", "french": "fr-FR",
    "de": "de-DE", "german": "de-DE",
    "pt": "pt-BR", "portuguese": "pt-BR",
    "it": "it-IT", "italian": "it-IT",
    "nl": "nl-NL", "dutch": "nl-NL",
    "pl": "pl-PL", "polish": "pl-PL",
    "ar": "ar-XA", "arabic": "ar-XA",
    "hi": "hi-IN", "hindi": "hi-IN",
    "ja": "ja-JP", "japanese": "ja-JP",
    "ko": "ko-KR", "korean": "ko-KR",
    "zh": "cmn-CN", "chinese": "cmn-CN",
    "ru": "ru-RU", "russian": "ru-RU",
    "tr": "tr-TR", "turkish": "tr-TR",
}

# Default Neural2 voices per BCP-47 code (female, high quality)
_DEFAULT_VOICES: dict[str, str] = {
    "en-US": "en-US-Neural2-F",
    "es-ES": "es-ES-Neural2-E",
    "fr-FR": "fr-FR-Neural2-E",
    "de-DE": "de-DE-Neural2-F",
    "pt-BR": "pt-BR-Neural2-C",
    "it-IT": "it-IT-Neural2-A",
    "nl-NL": "nl-NL-Standard-D",
    "pl-PL": "pl-PL-Standard-E",
    "ar-XA": "ar-XA-Neural2-A",
    "hi-IN": "hi-IN-Neural2-A",
    "ja-JP": "ja-JP-Neural2-B",
    "ko-KR": "ko-KR-Neural2-A",
    "cmn-CN": "cmn-CN-Neural2-D",
    "ru-RU": "ru-RU-Standard-E",
    "tr-TR": "tr-TR-Standard-E",
}


# ── Public API ────────────────────────────────────────────────────────────────

def generate_voiceovers_for_plan(
    plan: VideoPlan,
    output_dir: Path,
    settings: Settings,
) -> VideoPlan:
    """Generate Google TTS voiceover MP3s for every scene. Returns the mutated plan."""
    lang_code = _resolve_language_code(plan.language, settings.google_tts_language_code)
    voice_name = _resolve_voice_name(lang_code, settings.google_tts_voice_name)

    for scene in plan.scenes:
        scene_dir = output_dir / f"scene_{scene.scene_number:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        dest = scene_dir / "voiceover.mp3"

        audio_bytes = _synthesize(
            text=scene.voiceover_text,
            api_key=settings.google_tts_api_key,
            language_code=lang_code,
            voice_name=voice_name,
            speaking_rate=settings.google_tts_speaking_rate,
            pitch=settings.google_tts_pitch,
            audio_encoding=settings.google_tts_audio_encoding,
        )

        if audio_bytes:
            dest.write_bytes(audio_bytes)
            scene.voiceover_audio_path = str(dest)

        time.sleep(_REQUEST_DELAY)

    return plan


# ── Internal helpers ──────────────────────────────────────────────────────────

def _synthesize(
    text: str,
    api_key: str,
    language_code: str,
    voice_name: str,
    speaking_rate: float,
    pitch: float,
    audio_encoding: str,
) -> bytes | None:
    """Call the Google Cloud TTS REST API and return raw MP3 bytes."""
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": language_code,
            "name": voice_name,
            "ssmlGender": "FEMALE",
        },
        "audioConfig": {
            "audioEncoding": audio_encoding,
            "speakingRate": speaking_rate,
            "pitch": pitch,
        },
    }
    try:
        resp = requests.post(
            _GOOGLE_TTS_URL,
            params={"key": api_key},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        audio_content = resp.json().get("audioContent", "")
        return base64.b64decode(audio_content) if audio_content else None
    except requests.HTTPError as exc:
        import warnings
        warnings.warn(f"Google TTS failed for scene: {exc} — {resp.text[:200]}", stacklevel=2)
        return None
    except requests.RequestException as exc:
        import warnings
        warnings.warn(f"Google TTS request error: {exc}", stacklevel=2)
        return None


def _resolve_language_code(language: str, configured_code: str) -> str:
    """Return the BCP-47 code for the plan's language, falling back to the configured default."""
    return _LANGUAGE_MAP.get(language.lower(), configured_code)


def _resolve_voice_name(language_code: str, configured_voice: str) -> str:
    """Return the best available voice for the language code."""
    # If the configured voice explicitly matches the language, use it
    if configured_voice and configured_voice.startswith(language_code[:2]):
        return configured_voice
    return _DEFAULT_VOICES.get(language_code, configured_voice)
