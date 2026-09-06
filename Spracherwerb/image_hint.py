"""Shared best-effort SD Runner image generation with on-disk reuse.

Used by VisualVocabulary and SituationalDialogues. Every function returns None
on any failure (no client, unreachable, generation error) rather than raising --
callers already treat a missing image as a normal, gracefully-degraded outcome
(an activity that also has a text/no-image path).

Generation itself happens on MediaGenerationService's worker. A module waits
only for the item the learner is looking at, and queues the rest of its plan to
be drawn while the learner works through the earlier items -- so the wait, when
there is one, happens once per word rather than once per turn.
"""

import logging
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

from .media_generation import MediaPriority, find_cached

logger = logging.getLogger(__name__)

#: Upper bound on waiting for the current item. Past this the activity carries
#: on without a picture; the file still lands in the cache, so the next time
#: the same word comes round it is already there.
CURRENT_ITEM_TIMEOUT_S = 120.0


def _media_service(services: Any):
    return getattr(services, 'media', None)


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
    return find_cached(cache_dir, slug)


def generate_now(
    services: Any,
    cache_dir: Path,
    slug: str,
    prompt: str,
    group: Optional[str] = None,
    timeout: float = CURRENT_ITEM_TIMEOUT_S,
) -> Optional[str]:
    """Return a picture for *slug*, waiting for it if it is not drawn yet.

    For the item on screen now. A cached file returns immediately; otherwise
    this asks for the picture at NOW priority, ahead of any pre-generation, and
    waits.
    """
    cached = find_cached(cache_dir, slug)
    if cached:
        return cached
    service = _media_service(services)
    if service is None:
        return None
    try:
        job_id = service.request(
            slug, prompt, cache_dir=cache_dir, group=group,
            priority=MediaPriority.NOW)
        return service.wait_for(job_id, timeout=timeout)
    except Exception as e:
        logger.warning(f"Image generation failed for {slug!r}: {e}")
        return None


def cancel_pending(services: Any, group: str) -> None:
    """Drop queued pictures for *group*.

    Called when an activity ends: its remaining pre-generation is for words
    the learner is not going to be asked about now, and leaving it queued makes
    the next activity's picture wait behind work nobody wants. Anything already
    drawn stays in the cache.
    """
    service = _media_service(services)
    if service is None:
        return
    try:
        service.cancel_group(group)
    except Exception as e:
        logger.warning(f"Could not cancel pending generation for {group!r}: {e}")


def generate_ahead(
    services: Any,
    cache_dir: Path,
    items: Iterable[Tuple[str, str]],
    group: Optional[str] = None,
) -> None:
    """Queue pictures for items the learner has not reached yet.

    Never waits. Items already cached are skipped here rather than queued and
    resolved on the worker, so a warm cache costs nothing.
    """
    service = _media_service(services)
    if service is None:
        return
    wanted = [
        (slug, prompt) for slug, prompt in items
        if slug and not find_cached(cache_dir, slug)
    ]
    if not wanted:
        return
    try:
        service.request_ahead(wanted, cache_dir=cache_dir, group=group)
    except Exception as e:
        logger.warning(f"Could not queue pre-generation: {e}")
