"""Shared fixtures for testing the Spracherwerb application."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path BEFORE any other imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import tempfile
import shutil
from utils.config import config

def pytest_addoption(parser):
    parser.addoption(
        "--disable-tts",
        action="store_true",
        default=False,
        help="Disable TTS functionality for testing"
    )

@pytest.fixture(autouse=True)
def setup_tts_config(request):
    """Automatically set TTS configuration based on command line argument"""
    if request.config.getoption("--disable-tts"):
        config.disable_tts = True

@pytest.fixture(scope="session")
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture(scope="session")
def mock_llm():
    """Create a mock LLM instance for testing."""
    from extensions.llm import LLM
    return LLM()

@pytest.fixture(scope="session")
def mock_gutenberg():
    """Create a mock Gutenberg instance for testing."""
    from extensions.gutenberg import Gutenberg
    return Gutenberg()

@pytest.fixture(scope="session")
def mock_tatoeba():
    """Create a mock Tatoeba instance for testing."""
    from extensions.tatoeba import Tatoeba
    return Tatoeba()

@pytest.fixture(scope="session")
def mock_wiktionary():
    """Create a mock Wiktionary instance for testing."""
    from extensions.wiktionary import Wiktionary
    return Wiktionary()

@pytest.fixture(scope="session")
def mock_opensubtitles():
    """Create a mock OpenSubtitles instance for testing."""
    from extensions.opensubtitles import OpenSubtitles
    return OpenSubtitles()

@pytest.fixture(scope="session")
def mock_librivox():
    """Create a mock LibriVox instance for testing."""
    from extensions.librivox import LibriVox
    return LibriVox()

@pytest.fixture(scope="session")
def mock_forvo():
    """Create a mock Forvo instance for testing."""
    from extensions.forvo import Forvo
    return Forvo()

@pytest.fixture(scope="session")
def mock_wordnet():
    """Create a mock WordNet instance for testing."""
    from extensions.wordnet import WordNet
    return WordNet()

@pytest.fixture(scope="session")
def mock_languagetool():
    """Create a mock LanguageTool instance for testing."""
    from extensions.languagetool import LanguageTool
    return LanguageTool()

@pytest.fixture(scope="session")
def mock_wikimedia_commons():
    """Create a mock WikimediaCommons instance for testing."""
    from extensions.wikimedia_commons import WikimediaCommons
    return WikimediaCommons() 