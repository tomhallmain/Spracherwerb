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


def _patch_app_info_cache_singleton(monkeypatch, cache_instance) -> None:
    """Patch the app_info_cache singleton everywhere tests may hold a reference."""
    import utils

    cache_module = importlib.import_module("utils.app_info_cache")
    monkeypatch.setattr(cache_module, "app_info_cache", cache_instance)
    monkeypatch.setattr(utils, "app_info_cache", cache_instance)

    for module_name in (
        "Spracherwerb.prompter",
        "ui.translations_window",
    ):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        if hasattr(module, "app_info_cache"):
            monkeypatch.setattr(module, "app_info_cache", cache_instance)

    for name, module in list(sys.modules.items()):
        if not name.startswith("tests."):
            continue
        if hasattr(module, "app_info_cache"):
            monkeypatch.setattr(module, "app_info_cache", cache_instance)


def _patch_config_singleton(monkeypatch, config_instance) -> None:
    """Patch the config singleton (same package shadowing issue as app_info_cache)."""
    import utils

    config_module = importlib.import_module("utils.config")
    monkeypatch.setattr(config_module, "config", config_instance)
    monkeypatch.setattr(utils, "config", config_instance)

    for module_name in (
        "Spracherwerb.voice",
        "Spracherwerb.prompter",
        "Spracherwerb.language_tutor",
        "extensions.gutenberg_selector",
        "Spracherwerb.learning_spot_profile",
        "Spracherwerb.session_config",
        "Spracherwerb.session_context",
        "Spracherwerb.session_controller",
        "ui.app_style",
        "ui.config_panel",
        "ui.interaction_panel",
        "ui.translation_dialog",
        "ui.translations_window",
        "ui.gutenberg_search_window",
        "extensions.sd_runner_client",
        "tts.tts_runner",
        "tts.text_cleaner_ruleset",
        "library_data.blacklist",
        "utils.vocabulary_pool",
    ):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        if hasattr(module, "config"):
            monkeypatch.setattr(module, "config", config_instance)

    for name, module in list(sys.modules.items()):
        if not name.startswith("tests."):
            continue
        if hasattr(module, "config"):
            monkeypatch.setattr(module, "config", config_instance)


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

    from utils.app_info_cache import AppInfoCache

    new_cache = AppInfoCache()
    _patch_app_info_cache_singleton(monkeypatch, new_cache)

    config_module = importlib.import_module("utils.config")
    config_instance = config_module.Config()
    config_instance.backup_dir = str(backup_dir)
    if os.path.isfile(_blacklist_example_src):
        config_instance.blacklist_file = _blacklist_example_src
    config_instance.ignore_missing_api_keys = True
    if request.config.getoption("--disable-tts"):
        config_instance.disable_tts = True
    _patch_config_singleton(monkeypatch, config_instance)

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
