"""
Test environment bootstrap (cache/config paths, offscreen Qt, fake keyring).

Called at import time from ``tests/conftest.py`` and nested ``conftest.py`` files
so env vars exist before ``utils`` singletons load. Safe to call multiple times;
only the first call creates temp dirs.
"""

from __future__ import annotations

import atexit
import importlib
import os
import shutil
import tempfile
from pathlib import Path

_applied = False
_cleanup_tmp: str | None = None
_fake_keyring: "_FakeKeyring | None" = None


class _FakeKeyring:
    """In-memory stand-in for the OS credential store."""

    def __init__(self):
        self._store = {}

    def get_password(self, service_name, key):
        return self._store.get((service_name, key))

    def set_password(self, service_name, key, value):
        self._store[(service_name, key)] = value

    def delete_password(self, service_name, key):
        # The real backends raise when the entry is absent, and the encryptor's
        # quiet-delete helpers rely on that.
        if (service_name, key) not in self._store:
            raise Exception(f"No such password: {service_name}:{key}")
        del self._store[(service_name, key)]

    def clear(self):
        self._store.clear()


def install_fake_keyring() -> "_FakeKeyring":
    """Point ``utils.encryptor`` at an in-memory credential store.

    Anything that encrypts or decrypts reaches ``utils/encryptor.py``, which
    talks to the real Windows Credential Manager / macOS keychain / Secret
    Service. Tests write their cache to a temp directory, but the *keys* for it
    would go to the live store -- and because key material is consolidated into
    a key store file, the first test to touch it would migrate the real
    keychain items into a per-test temp directory and then DELETE THE
    ORIGINALS, destroying the developer's key material along with access to
    their real ``app_info_cache.enc``.

    Installed here rather than through a fixture so there is no window, however
    brief, in which a test can reach the real store.
    """
    global _fake_keyring
    if _fake_keyring is None:
        # import_module, because a name re-exported by utils/__init__.py
        # shadows the submodule it came from. Assigning ``keyring`` on such a
        # shadowing object would succeed and leave the real credential store in
        # place, which is the one failure here that must not be silent.
        encryptor_module = importlib.import_module("utils.encryptor")

        _fake_keyring = _FakeKeyring()
        encryptor_module.keyring = _fake_keyring
    return _fake_keyring


def _pin_key_backup_dir() -> None:
    """Keep automatic key backups inside the throwaway test tree.

    The encryptor takes an off-drive backup after every key store write, and
    with no destination set it picks the first writable external drive it finds
    -- the developer's actual USB stick.
    """
    os.environ.setdefault(
        "SPRACHERWERB_KEY_BACKUP_DIR",
        os.path.join(os.environ["SPRACHERWERB_CACHE_DIR"], "key_backup"),
    )


def apply() -> None:
    global _applied, _cleanup_tmp
    if _applied or os.environ.get("SPRACHERWERB_CACHE_DIR"):
        _applied = True
        _pin_key_backup_dir()
        install_fake_keyring()
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
    _pin_key_backup_dir()
    install_fake_keyring()


def project_root() -> str:
    return str(Path(__file__).resolve().parent.parent)
