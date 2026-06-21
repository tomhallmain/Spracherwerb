"""
Test environment bootstrap (cache/config paths, offscreen Qt).

Called at import time from ``tests/conftest.py`` and nested ``conftest.py`` files
so env vars exist before ``utils`` singletons load. Safe to call multiple times;
only the first call creates temp dirs.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_applied = False
_cleanup_tmp: str | None = None


def apply() -> None:
    global _applied, _cleanup_tmp
    if _applied or os.environ.get("SPRACHERWERB_CACHE_DIR"):
        _applied = True
        return

    project_root = Path(__file__).resolve().parent.parent
    config_example = project_root / "configs" / "config_example.json"

    _cleanup_tmp = tempfile.mkdtemp(prefix="spracherwerb_tests_")
    os.environ["SPRACHERWERB_CACHE_DIR"] = os.path.join(_cleanup_tmp, "cache")
    os.environ["SPRACHERWERB_CONFIGS_DIR"] = os.path.join(_cleanup_tmp, "configs")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.makedirs(os.environ["SPRACHERWERB_CACHE_DIR"], exist_ok=True)
    os.makedirs(os.environ["SPRACHERWERB_CONFIGS_DIR"], exist_ok=True)
    backup_dir = os.path.join(os.environ["SPRACHERWERB_CACHE_DIR"], "backup")
    os.makedirs(backup_dir, exist_ok=True)
    if config_example.is_file():
        config_dest = os.path.join(os.environ["SPRACHERWERB_CONFIGS_DIR"], "config.json")
        shutil.copy(config_example, config_dest)
        try:
            import json

            with open(config_dest, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["backup_dir"] = backup_dir
            blacklist_example = project_root / "library_data" / "data" / "blacklist_example.json"
            if blacklist_example.is_file():
                payload["blacklist_file"] = str(blacklist_example)
            payload["ignore_missing_api_keys"] = True
            with open(config_dest, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
        except Exception:
            pass
    atexit.register(shutil.rmtree, _cleanup_tmp, True)
    _applied = True


def project_root() -> str:
    return str(Path(__file__).resolve().parent.parent)
