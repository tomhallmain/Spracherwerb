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
