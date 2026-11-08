"""Resolve on-disk cache, config and log locations (overridable for tests).

Each location has an environment override; the test suite sets all of them
to a throwaway directory so no test reads or writes the user's own files:
SPRACHERWERB_CACHE_DIR, SPRACHERWERB_CONFIGS_DIR and SPRACHERWERB_LOG_DIR.
"""

import os
from pathlib import Path
from typing import Optional, Union

# Cache root when SPRACHERWERB_CACHE_DIR is unset, relative to the working
# directory the app is started from.
DEFAULT_CACHE_ROOT = 'cache'


def spracherwerb_cache_dir() -> Optional[str]:
    return os.environ.get("SPRACHERWERB_CACHE_DIR")


def spracherwerb_configs_dir() -> Optional[str]:
    return os.environ.get("SPRACHERWERB_CONFIGS_DIR")


def spracherwerb_log_dir() -> Optional[str]:
    return os.environ.get("SPRACHERWERB_LOG_DIR")


def resolve_cache_file(filename: str) -> str:
    """Return an absolute path for a cache file under the override directory."""
    base = spracherwerb_cache_dir()
    if base:
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, filename)
    return filename


def resolve_cache_subdir(name: str, default: Union[str, Path, None] = None) -> Path:
    """Directory *name* under the override directory when one is set.

    Otherwise *default* if given, else ``cache/<name>``. Resolved per call, so
    it follows SPRACHERWERB_CACHE_DIR whenever that is set. Not created here;
    the caller creates it when it first writes.
    """
    override = spracherwerb_cache_dir()
    if override:
        return Path(override) / name
    if default is not None:
        return Path(default)
    return Path(DEFAULT_CACHE_ROOT) / name


class CachePath:
    """Class attribute that resolves to a path under the cache root on each read.

    ``CACHE_DIR = CachePath('gutenberg')`` and
    ``CACHE_FILE = CachePath('gutenberg', 'books.json')``. A plain ``Path``
    class attribute would be fixed at import, before a test can point
    SPRACHERWERB_CACHE_DIR elsewhere. Assigning the attribute on an instance
    still overrides it for that instance.
    """

    def __init__(self, subdir: str, filename: Optional[str] = None,
                 default: Union[str, Path, None] = None):
        self.subdir = subdir
        self.filename = filename
        self.default = default

    def __get__(self, obj, objtype=None) -> Path:
        directory = resolve_cache_subdir(self.subdir, self.default)
        return directory / self.filename if self.filename else directory
