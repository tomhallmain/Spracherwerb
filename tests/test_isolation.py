"""Verify config and app_info_cache isolation for every test run."""

import os

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
