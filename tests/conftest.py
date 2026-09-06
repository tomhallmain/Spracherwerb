"""
Root conftest for the Spracherwerb test suite.

Env vars must be set at module load time — before app singletons import — because
``app_info_cache``, ``config``, and translation cache paths are created on first import.
Nested conftest files mirror the same bootstrap for alternate collection orders.
"""

import importlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Project root on sys.path (see also pythonpath / importmode in pytest.ini)
# ---------------------------------------------------------------------------
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ---------------------------------------------------------------------------
# Bootstrap temp cache/config before any utils singleton import
# ---------------------------------------------------------------------------
_bootstrap_spec = importlib.util.spec_from_file_location(
    "spracherwerb_tests_bootstrap_env",
    os.path.join(os.path.dirname(__file__), "bootstrap_env.py"),
)
_bootstrap_mod = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(_bootstrap_mod)
_bootstrap_mod.apply()

_config_example_src = os.path.join(_project_root, "configs", "config_example.json")
_blacklist_example_src = os.path.join(
    _project_root, "library_data", "data", "blacklist_example.json"
)


def repoint_singleton_bindings(monkeypatch, attr_name, old_obj, new_obj) -> None:
    """Repoint every module-level binding of *old_obj* to *new_obj*.

    A module doing ``from utils.config import config`` at import time holds its
    own reference, so patching the source module alone leaves that binding on
    the un-isolated singleton -- which is never reset between tests, so its
    values leak into whatever runs next and a test passes for the wrong reason.

    Sweeping sys.modules covers every such binding, including the ``utils``
    package's re-exports and the test modules themselves. A hand-maintained
    list of modules to patch is the obvious alternative, and it goes out of
    date silently: ``utils.translation_data_manager`` holds a ``config``
    binding whose ``backup_dir`` is the user's real one, so missing it has a
    test writing a translations backup there. The identity check touches only
    bindings to the exact old object, and modules imported later reach the new
    object through the already-patched source module.

    Two things it cannot reach: a reference copied onto an instance attribute
    (``self.config = config``), which needs its owner rebuilt; and a module
    first imported *during* a test, which binds that test's instance --
    monkeypatch never set that binding, so it survives teardown and later
    sweeps no longer recognise it. That second one only bites a module reached
    exclusively by a lazy import; anything a test module imports at the top is
    in sys.modules before the first sweep runs.
    """
    for module in list(sys.modules.values()):
        try:
            if getattr(module, attr_name, None) is old_obj:
                monkeypatch.setattr(module, attr_name, new_obj)
        except Exception:
            continue


def pytest_addoption(parser):
    parser.addoption(
        "--disable-tts",
        action="store_true",
        default=False,
        help="Disable TTS functionality for testing",
    )


def _write_isolated_config(configs_dir: Path, backup_dir: Path) -> None:
    """Copy config_example.json into *configs_dir* with test-safe paths."""
    if not os.path.isfile(_config_example_src):
        return
    config_dest = configs_dir / "config.json"
    shutil.copy(_config_example_src, config_dest)
    try:
        import json

        with open(config_dest, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["backup_dir"] = str(backup_dir)
        if os.path.isfile(_blacklist_example_src):
            payload["blacklist_file"] = _blacklist_example_src
        payload["ignore_missing_api_keys"] = True
        with open(config_dest, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def isolated_singletons(tmp_path, monkeypatch, request):
    """Point app singletons at a fresh per-test temp directory."""
    cache_dir = tmp_path / "cache"
    configs_dir = tmp_path / "configs"
    backup_dir = tmp_path / "backup"
    cache_dir.mkdir()
    configs_dir.mkdir()
    backup_dir.mkdir()
    _write_isolated_config(configs_dir, backup_dir)

    monkeypatch.setenv("SPRACHERWERB_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("SPRACHERWERB_CONFIGS_DIR", str(configs_dir))
    monkeypatch.setenv("SPRACHERWERB_KEY_BACKUP_DIR", str(tmp_path / "key_backup"))

    # The encryptor caches key material and passphrases per (service, app) for
    # the life of the process, so material written by one test would answer
    # another's read. The fake keyring is emptied for the same reason: each test
    # gets a fresh cache directory, and a passphrase left behind by an earlier
    # test would look like "keys existed here once" and block key generation.
    from utils.encryptor import clear_key_store_cache

    clear_key_store_cache()
    _bootstrap_mod.install_fake_keyring().clear()

    # importlib rather than ``import utils.config as config_module``:
    # utils/__init__.py re-exports both singletons, so the package attribute
    # ``utils.config`` is the Config instance and shadows the submodule of the
    # same name. import_module goes to sys.modules and returns the module.
    cache_module = importlib.import_module("utils.app_info_cache")
    config_module = importlib.import_module("utils.config")

    repoint_singleton_bindings(
        monkeypatch, "app_info_cache",
        cache_module.app_info_cache, cache_module.AppInfoCache(),
    )

    config_instance = config_module.Config()
    config_instance.backup_dir = str(backup_dir)
    if os.path.isfile(_blacklist_example_src):
        config_instance.blacklist_file = _blacklist_example_src
    config_instance.ignore_missing_api_keys = True
    if request.config.getoption("--disable-tts"):
        config_instance.disable_tts = True
    repoint_singleton_bindings(
        monkeypatch, "config", config_module.config, config_instance
    )

    yield


@pytest.fixture(scope="session")
def temp_cache_dir():
    """Legacy fixture: session temp dir (prefer ``isolated_singletons`` per test)."""
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="spracherwerb_tests_legacy_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def mock_llm():
    from extensions.llm import LLM
    from utils.config import config

    return LLM.from_config(config, state_key="tests")


@pytest.fixture(scope="session")
def mock_gutenberg():
    from extensions.gutenberg import Gutenberg

    return Gutenberg()


@pytest.fixture(scope="session")
def mock_tatoeba():
    from extensions.tatoeba import Tatoeba

    return Tatoeba()


@pytest.fixture(scope="session")
def mock_wiktionary():
    from extensions.wiktionary import Wiktionary

    return Wiktionary()


@pytest.fixture(scope="session")
def mock_opensubtitles():
    from extensions.opensubtitles import OpenSubtitles

    return OpenSubtitles()


@pytest.fixture(scope="session")
def mock_librivox():
    from extensions.librivox import LibriVox

    return LibriVox()


@pytest.fixture(scope="session")
def mock_forvo():
    from extensions.forvo import Forvo

    return Forvo()


@pytest.fixture(scope="session")
def mock_wordnet():
    from extensions.wordnet import WordNet

    return WordNet()


@pytest.fixture(scope="session")
def mock_languagetool():
    from extensions.languagetool import LanguageTool

    return LanguageTool()


@pytest.fixture(scope="session")
def mock_wikimedia_commons():
    from extensions.wikimedia_commons import WikimediaCommons

    return WikimediaCommons()


def pytest_sessionfinish(session, exitstatus):
    """Remove disposable TTS artifacts left in tts_output by integration tests."""
    from tts.output_cleanup import cleanup_default_output_directory

    cleanup_default_output_directory()
