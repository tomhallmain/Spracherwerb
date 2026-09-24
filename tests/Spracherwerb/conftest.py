"""Bootstrap env when ``tests/Spracherwerb`` is collected without the root conftest."""

import importlib.util
import os

if "SPRACHERWERB_CACHE_DIR" not in os.environ:
    _spec = importlib.util.spec_from_file_location(
        "spracherwerb_tests_bootstrap_env",
        os.path.join(os.path.dirname(__file__), "..", "bootstrap_env.py"),
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.apply()


import pytest

from Spracherwerb.activity_registry import ActivityRegistry


@pytest.fixture(autouse=True)
def restore_activity_registry():
    """Put the process-wide registry back as it was before each test.

    Test files reset it to placeholders for a clean slate, and a reset on
    teardown would leave every later test in the process with placeholders
    in place of the real modules registered at import.
    """
    module_classes = dict(ActivityRegistry._module_classes)
    defaults_registered = ActivityRegistry._defaults_registered
    yield
    ActivityRegistry._module_classes.clear()
    ActivityRegistry._module_classes.update(module_classes)
    ActivityRegistry._defaults_registered = defaults_registered
