"""Resolve on-disk cache and config locations (overridable for tests)."""

import os
from typing import Optional


def spracherwerb_cache_dir() -> Optional[str]:
    return os.environ.get("SPRACHERWERB_CACHE_DIR")


def resolve_cache_file(filename: str) -> str:
    """Return an absolute path for a cache file under the override directory."""
    base = spracherwerb_cache_dir()
    if base:
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, filename)
    return filename
