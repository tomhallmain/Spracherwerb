"""Bootstrap env when ``tests/ui`` is collected without the root conftest.

Also hosts the shared QApplication fixture: Qt allows one per process, so it
cannot live in an individual test module."""

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
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """The process-wide QApplication every widget test needs.

    bootstrap_env sets QT_QPA_PLATFORM=offscreen, so this needs no display.
    """
    return QApplication.instance() or QApplication([])
