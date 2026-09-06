"""Config loading, focused on how a JSON null is treated.

`set_values` coerces each key to a declared type. A null coerced by `str`
becomes the string "None", which reads as a real value everywhere downstream
and silently defeats the `is None` fallbacks in `Config.__init__` -- so a null
has to mean "not set" and leave the default alone.
"""

import json
import os

import pytest

from utils.config import Config

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CONFIG_EXAMPLE = os.path.join(_PROJECT_ROOT, "configs", "config_example.json")
_BLACKLIST_EXAMPLE = os.path.join(
    _PROJECT_ROOT, "library_data", "data", "blacklist_example.json")


#: Sentinel for "delete this key" in config_from(), distinct from a JSON null.
_REMOVE = object()


@pytest.fixture
def config_from(tmp_path):
    """Build a Config from config_example.json with *overrides* applied.

    The example ships real user paths -- ``backup_dir`` and ``blacklist_file``
    both expand ``{HOME}`` -- and a Config built straight from it resolves them
    against the developer's own home directory. Config.__init__ only stats
    them, but ``backup_dir`` is where TranslationDataManager writes its backup,
    so anything reached from such a config would write there for real. Pinned
    into tmp_path here for the same reason tests/conftest.py pins them for the
    singleton.
    """
    def build(**overrides):
        with open(_CONFIG_EXAMPLE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir(exist_ok=True)
        payload["backup_dir"] = str(backup_dir)
        payload["blacklist_file"] = str(_BLACKLIST_EXAMPLE)
        for key, value in overrides.items():
            if value is _REMOVE:
                payload.pop(key, None)
            else:
                payload[key] = value
        path = tmp_path / "config.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return Config(config_path=str(path))
    return build


class TestNullMeansNotSet:
    def test_a_null_string_does_not_become_the_word_none(self, config_from):
        config = config_from(sd_runner_client_id=None)
        assert config.sd_runner_client_id is None

    def test_source_language_null_reaches_the_system_default(self, config_from):
        """The fallback in __init__ is `if self.source_language is None`, which
        never fires once the null has been coerced to a string."""
        config = config_from(source_language=None)
        assert config.source_language is not None
        assert config.source_language != "None"

    def test_a_null_int_keeps_its_default(self, config_from):
        default = config_from().font_size
        config = config_from(font_size=None)
        assert config.font_size == default

    def test_a_null_bool_keeps_its_default(self, config_from):
        default = config_from().enable_dark_mode
        config = config_from(enable_dark_mode=None)
        assert config.enable_dark_mode == default


class TestFixtureIsolation:
    """The fixture must not hand back a config aimed at real user data."""

    def test_backup_dir_is_inside_the_test_directory(self, config_from, tmp_path):
        config = config_from()
        assert config.backup_dir is not None
        assert str(config.backup_dir).startswith(str(tmp_path))

    def test_backup_dir_is_not_the_one_the_example_ships(self, config_from):
        """Naming the real path rather than excluding a directory tree: on
        Windows pytest's tmp_path lives under the home directory too, so
        "outside ~" says nothing about isolation."""
        with open(_CONFIG_EXAMPLE, "r", encoding="utf-8") as handle:
            shipped = json.load(handle)["backup_dir"]
        real = os.path.normpath(
            shipped.replace("{HOME}", os.path.expanduser("~")))
        config = config_from()
        assert os.path.normpath(config.backup_dir).casefold() != real.casefold()


class TestValuesStillLoad:
    def test_a_real_string_is_applied(self, config_from):
        config = config_from(sd_runner_client_id="my-laptop")
        assert config.sd_runner_client_id == "my-laptop"

    def test_a_real_int_is_applied(self, config_from):
        config = config_from(server_port=6123)
        assert config.server_port == 6123

    def test_a_numeric_string_is_still_coerced(self, config_from):
        """Coercion is the point of the type argument; only null opts out."""
        config = config_from(server_port="6123")
        assert config.server_port == 6123

    def test_a_missing_key_keeps_its_default(self, config_from):
        config = config_from(sd_runner_client_id=_REMOVE)
        assert config.sd_runner_client_id is None
