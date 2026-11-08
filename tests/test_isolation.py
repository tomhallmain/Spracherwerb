"""Verify config and app_info_cache isolation for every test run."""

import importlib
import os

import pytest

from utils.translation_data_manager import TranslationDataManager


def test_config_and_cache_use_per_test_directories(tmp_path):
    from utils.app_info_cache import app_info_cache
    from utils.config import config

    cache_dir = tmp_path / "cache"
    assert os.environ["SPRACHERWERB_CACHE_DIR"] == str(cache_dir)
    assert os.environ["SPRACHERWERB_CONFIGS_DIR"] == str(tmp_path / "configs")
    assert str(config.config_path).startswith(str(tmp_path / "configs"))
    assert config.backup_dir == str(tmp_path / "backup")
    assert config.ignore_missing_api_keys is True
    assert app_info_cache._cache_loc.startswith(str(cache_dir))
    assert app_info_cache._json_loc.startswith(str(cache_dir))


def test_translation_data_manager_uses_isolated_cache(tmp_path):
    manager = TranslationDataManager()
    assert str(manager.cache_dir).startswith(str(tmp_path / "cache"))
    assert str(manager.data_file).startswith(str(tmp_path / "cache"))


# Every client keeping an on-disk cache, as (module, class, path attributes).
_EXTENSION_CACHES = [
    ("extensions.common_voice", "CommonVoice", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.forvo", "Forvo", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.gutenberg", "Gutenberg", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.languagetool", "LanguageTool", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.librivox", "LibriVox", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.opensubtitles", "OpenSubtitles", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.tatoeba", "Tatoeba", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.unilang", "UniLang", ("CACHE_DIR", "RESOURCES_CACHE", "FORUM_CACHE")),
    ("extensions.wikimedia_commons", "WikimediaCommons", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.wiktionary", "Wiktionary", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.wordnet", "WordNet", ("CACHE_DIR", "CACHE_FILE")),
    ("extensions.wordreference", "WordReference", ("CACHE_DIR", "CACHE_FILE")),
]


@pytest.mark.parametrize(("module_name", "class_name", "attributes"), _EXTENSION_CACHES)
def test_extension_caches_use_isolated_cache(tmp_path, module_name, class_name, attributes):
    client_class = getattr(importlib.import_module(module_name), class_name)
    for attribute in attributes:
        assert str(getattr(client_class, attribute)).startswith(str(tmp_path / "cache")), attribute


def test_activity_image_caches_use_isolated_cache(tmp_path):
    from Spracherwerb import situational_dialogues, visual_vocabulary

    for module in (situational_dialogues, visual_vocabulary):
        assert str(module.image_cache_dir()).startswith(str(tmp_path / "cache"))


def test_learning_memory_uses_isolated_cache(tmp_path):
    from Spracherwerb import learning_memory

    assert learning_memory._memory_file().startswith(str(tmp_path / "cache"))


def test_llm_history_uses_isolated_cache(tmp_path):
    from extensions.llm import LLM

    assert LLM().prompt_response_history_file.startswith(str(tmp_path / "cache"))


def test_tts_output_uses_isolated_cache(tmp_path):
    from tts.output_cleanup import default_output_directory

    assert default_output_directory().startswith(str(tmp_path / "cache"))


def test_piper_voices_use_isolated_configs(tmp_path):
    from tts.providers.piper import _default_voices_dir

    assert str(_default_voices_dir()).startswith(str(tmp_path / "configs"))


def test_logs_go_to_the_test_tree():
    """Loggers open their file at first import, so the bootstrap pins the directory first."""
    import logging

    import utils.config  # noqa: F401 -- creates the "spracherwerb.config" logger at import

    file_handlers = [
        handler for handler in logging.getLogger("spracherwerb.config").handlers
        if isinstance(handler, logging.FileHandler)
    ]
    assert file_handlers
    for handler in file_handlers:
        assert handler.baseFilename.startswith(os.environ["SPRACHERWERB_LOG_DIR"])


def test_cache_path_instance_assignment_overrides(tmp_path):
    """Tests redirect one client's cache by assigning on the instance."""
    from utils.cache_paths import CachePath

    class Client:
        CACHE_DIR = CachePath("client")

    client = Client()
    client.CACHE_DIR = tmp_path / "elsewhere"
    assert client.CACHE_DIR == tmp_path / "elsewhere"
    assert Client.CACHE_DIR == tmp_path / "cache" / "client"
