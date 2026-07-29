"""Shared best-effort SD Runner image generation with on-disk reuse.

Used by VisualVocabulary and SituationalDialogues: check reachability once
per session, reuse a matching cached file for a given slug when one already
exists, and otherwise request a new generation. Every function returns None
on any failure (no client, unreachable, generation error) rather than
raising -- callers already treat a missing image as a normal, gracefully-
degraded outcome (an activity that also has a text/no-image path).
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp")


def is_sd_available(services: Any) -> bool:
    sd_client = getattr(services, 'sd_client', None)
    if sd_client is None:
        return False
    try:
        return sd_client.is_reachable()
    except Exception as e:
        logger.warning(f"SD Runner reachability check failed: {e}")
        return False


def find_cached_image(cache_dir: Path, slug: str) -> Optional[str]:
    for ext in _IMAGE_EXTENSIONS:
        candidate = cache_dir / f"{slug}.{ext}"
        if candidate.exists():
            return str(candidate)
    return None


def request_generation(services: Any, cache_dir: Path, slug: str, prompt: str) -> Optional[str]:
    """Request a new image via services.sd_client. Does not check the cache
    first -- callers that want reuse should call find_cached_image() first."""
    sd_client = getattr(services, 'sd_client', None)
    if sd_client is None:
        return None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        return sd_client.generate_image(
            positive_prompt=prompt, target_dir=str(cache_dir), filename=slug)
    except Exception as e:
        logger.warning(f"Image generation failed for {slug!r}: {e}")
        return None
