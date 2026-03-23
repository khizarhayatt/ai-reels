"""Pexels visual agent — searches and downloads B-roll for every scene."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Union

import requests

from config import PLATFORM_CONFIGS, Settings
from models.video_plan import PexelsImage, PexelsVideo, Scene, VideoPlan

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_SEARCH = "https://api.pexels.com/v1/search"

# Seconds to wait between Pexels requests (free tier: 200 req/hr)
_REQUEST_DELAY = 0.5


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_visuals_for_plan(
    plan: VideoPlan,
    output_dir: Path,
    settings: Settings,
    prefer_video: bool = True,
) -> VideoPlan:
    """Download Pexels visuals for every scene. Returns the mutated plan."""
    orientation = _orientation_from_platform(plan.platform)
    for scene in plan.scenes:
        scene_dir = output_dir / f"scene_{scene.scene_number:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        if prefer_video:
            visuals = search_pexels_videos(
                query=scene.pexels_query,
                api_key=settings.pexels_api_key,
                orientation=orientation,
                per_page=settings.pexels_per_page,
                min_duration=settings.pexels_video_min_duration,
                max_duration=settings.pexels_video_max_duration,
            )
        else:
            visuals = []

        if not visuals:
            visuals = search_pexels_photos(
                query=scene.pexels_query,
                api_key=settings.pexels_api_key,
                orientation=orientation,
                per_page=settings.pexels_per_page,
            )

        downloaded: list[Union[PexelsVideo, PexelsImage]] = []
        for i, asset in enumerate(visuals[:2]):  # Download top 2 results per scene
            ext = "mp4" if isinstance(asset, PexelsVideo) else "jpg"
            dest = scene_dir / f"visual_{i + 1}.{ext}"
            try:
                download_asset(asset.download_url, dest)
                asset.local_path = str(dest)
                downloaded.append(asset)
            except DownloadError:
                pass  # Skip failed downloads gracefully

        scene.visuals = downloaded
        time.sleep(_REQUEST_DELAY)

    return plan


def search_pexels_videos(
    query: str,
    api_key: str,
    orientation: str,
    per_page: int = 5,
    min_duration: int = 3,
    max_duration: int = 15,
) -> list[PexelsVideo]:
    """Search Pexels for videos matching query. Returns list of PexelsVideo."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page,
        "size": "medium",
    }
    try:
        resp = requests.get(PEXELS_VIDEO_SEARCH, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    results = []
    for v in resp.json().get("videos", []):
        duration = v.get("duration", 0)
        if not (min_duration <= duration <= max_duration):
            continue
        best_file = _select_best_video_file(v.get("video_files", []), orientation)
        if not best_file:
            continue
        results.append(PexelsVideo(
            video_id=v["id"],
            url=v.get("url", ""),
            duration=duration,
            width=v.get("width", 0),
            height=v.get("height", 0),
            download_url=best_file["link"],
        ))
    return results


def search_pexels_photos(
    query: str,
    api_key: str,
    orientation: str,
    per_page: int = 5,
) -> list[PexelsImage]:
    """Fallback photo search when no suitable videos are found."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page,
        "size": "medium",
    }
    try:
        resp = requests.get(PEXELS_PHOTO_SEARCH, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    results = []
    for p in resp.json().get("photos", []):
        src = p.get("src", {})
        download_url = src.get("original") or src.get("large2x") or src.get("large", "")
        if not download_url:
            continue
        results.append(PexelsImage(
            image_id=p["id"],
            url=p.get("url", ""),
            photographer=p.get("photographer", ""),
            download_url=download_url,
        ))
    return results


def download_asset(url: str, dest_path: Path, timeout: int = 30) -> Path:
    """Stream-download a Pexels asset to dest_path."""
    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise DownloadError(f"Failed to download {url}: {exc}") from exc

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest_path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _select_best_video_file(video_files: list[dict], target_orientation: str) -> dict | None:
    """Pick the highest-quality video file matching the target orientation."""
    if not video_files:
        return None

    quality_rank = {"hd": 3, "full_hd": 4, "4k": 5, "sd": 2, "mobile": 1}
    is_portrait = target_orientation == "portrait"

    def score(f: dict) -> int:
        w, h = f.get("width", 0), f.get("height", 0)
        orientation_match = (h > w) == is_portrait
        q = quality_rank.get(f.get("quality", "sd"), 1)
        return q * (2 if orientation_match else 1)

    return max(video_files, key=score, default=None)


def _orientation_from_platform(platform: str) -> str:
    cfg = PLATFORM_CONFIGS.get(platform)
    return cfg.orientation if cfg else "landscape"


class DownloadError(IOError):
    """Raised when a Pexels asset download fails."""
