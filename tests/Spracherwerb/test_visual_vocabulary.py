"""Tests for VisualVocabulary, the image-mediated recall activity."""

import pytest

from Spracherwerb import visual_vocabulary
from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.learning_memory import LearningMemory
from Spracherwerb.media_generation import MediaGenerationService
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.visual_vocabulary import VisualVocabulary


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture(autouse=True)
def clean_learning_memory():
    before = dict(LearningMemory.vocabulary_learned)
    LearningMemory.vocabulary_learned = {}
    yield
    LearningMemory.vocabulary_learned = before


@pytest.fixture(autouse=True)
def isolated_image_cache(tmp_path, monkeypatch):
    """Redirect the module's image cache dir so tests never touch the real cache/ tree."""
    monkeypatch.setattr(visual_vocabulary, "IMAGE_CACHE_DIR", tmp_path / "visual_vocabulary")


class FakeVocabularyPool:
    def __init__(self, entries, session_limit=20):
        self._entries = entries
        self._session_limit = session_limit
        self.recorded = []

    def get_review_candidates(self, source_language, target_language, limit=20,
                               exclude=None, shuffle=True):
        return list(self._entries[:limit])

    def record_word_result(self, target_language, word, *, outcome="reviewed"):
        self.recorded.append((target_language, word, outcome))

    def default_session_limit(self):
        return self._session_limit


class FakeSDClient:
    """Stand-in for extensions.sd_runner_client.SDRunnerClient."""

    def __init__(self, reachable=True, image_path_by_prompt=None):
        self._reachable = reachable
        self._image_path_by_prompt = image_path_by_prompt or {}
        self.reachable_checks = 0
        self.generate_calls = []

    def is_reachable(self):
        self.reachable_checks += 1
        return self._reachable

    def generate_image(self, positive_prompt, target_dir, filename, negative_prompt=None,
                        timeout=120.0, poll_interval=1.0):
        self.generate_calls.append((positive_prompt, target_dir, filename))
        return self._image_path_by_prompt.get(positive_prompt)


#: Services built during a test, shut down by the autouse fixture below.
_media_services = []


@pytest.fixture(autouse=True)
def shutdown_media_services():
    """Stop each test's generation worker; they are daemon threads otherwise
    left running for the rest of the session."""
    yield
    while _media_services:
        _media_services.pop().shutdown()


def make_services(entries, sd_client=None, proficiency_level="intermediate",
                   source_language="en", target_language="de", enable_visual_learning=True):
    pool = FakeVocabularyPool(entries)
    session_config = SessionConfig({
        "source_language": source_language,
        "target_language": target_language,
        "proficiency_level": proficiency_level,
        "enable_visual_learning": enable_visual_learning,
    })
    media = None
    if sd_client is not None:
        media = MediaGenerationService(sd_client=sd_client)
        _media_services.append(media)
    services = ModuleServices(
        prompter=None,
        voice=None,
        session_config=session_config,
        session_context=None,
        vocabulary_pool=pool,
        sd_client=sd_client,
        media=media,
    )
    return services, pool


HUND_ENTRY = {"source_text": "dog", "translated_text": "Hund", "target_article": "der"}
HUND_PROMPT = "dog, simple clear illustration, single subject, plain background"


class TestVisualVocabularyRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(VisualVocabulary)
        assert ActivityRegistry.is_implemented(ActivityType.VISUAL_VOCABULARY)
        module = ActivityRegistry.create(ActivityType.VISUAL_VOCABULARY)
        assert isinstance(module, VisualVocabulary)


class TestVisualVocabularyEmptyPool:
    def test_start_with_no_candidates_does_not_expect_a_response(self):
        services, _pool = make_services([], sd_client=None)
        module = VisualVocabulary()

        result = module.start(services)

        assert result.expects_response is False
        assert "no saved vocabulary" in result.text_response.lower()


class TestVisualVocabularyWithoutSD:
    def test_falls_back_to_text_prompt_when_sd_client_is_none(self):
        services, _pool = make_services([HUND_ENTRY], sd_client=None)
        module = VisualVocabulary()

        result = module.start(services)

        assert result.media_path is None
        assert "Wie sagt man" in result.text_response  # VocabularyBuilder-style text fallback

    def test_falls_back_to_text_prompt_when_sd_unreachable(self):
        sd_client = FakeSDClient(reachable=False)
        services, _pool = make_services([HUND_ENTRY], sd_client=sd_client)
        module = VisualVocabulary()

        result = module.start(services)

        assert result.media_path is None
        assert sd_client.generate_calls == []

    def test_disabled_by_config_skips_sd_entirely(self):
        sd_client = FakeSDClient(reachable=True)
        services, _pool = make_services(
            [HUND_ENTRY], sd_client=sd_client, enable_visual_learning=False)
        module = VisualVocabulary()

        module.start(services)

        assert sd_client.reachable_checks == 0
        assert sd_client.generate_calls == []


class TestVisualVocabularyWithSD:
    def test_uses_image_prompt_when_generation_succeeds(self):
        sd_client = FakeSDClient(
            reachable=True, image_path_by_prompt={HUND_PROMPT: "/tmp/de_hund.png"})
        services, _pool = make_services(
            [HUND_ENTRY], sd_client=sd_client, proficiency_level="intermediate")
        module = VisualVocabulary()

        result = module.start(services)

        assert result.media_path == "/tmp/de_hund.png"
        assert result.text_response == 'Wie heißt das auf Deutsch? (What is this called in German?)'
        assert len(sd_client.generate_calls) == 1

    def test_beginner_direction_with_image_asks_for_source_meaning(self):
        sd_client = FakeSDClient(
            reachable=True, image_path_by_prompt={HUND_PROMPT: "/tmp/de_hund.png"})
        services, _pool = make_services(
            [HUND_ENTRY], sd_client=sd_client, proficiency_level="beginner")
        module = VisualVocabulary()

        result = module.start(services)

        assert result.text_response == (
            'Was zeigt das Bild? (What does the picture show, in English?)'
        )

    def test_reuses_cached_image_without_regenerating(self, tmp_path):
        cache_dir = tmp_path / "visual_vocabulary"
        cache_dir.mkdir()
        cached_file = cache_dir / "de_hund.png"
        cached_file.write_bytes(b"fake-image-bytes")

        sd_client = FakeSDClient(reachable=True)
        services, _pool = make_services([HUND_ENTRY], sd_client=sd_client)
        module = VisualVocabulary()

        result = module.start(services)

        assert result.media_path == str(cached_file)
        assert sd_client.generate_calls == []

    def test_falls_back_to_text_when_generation_returns_no_path(self):
        sd_client = FakeSDClient(reachable=True, image_path_by_prompt={})
        services, _pool = make_services([HUND_ENTRY], sd_client=sd_client)
        module = VisualVocabulary()

        result = module.start(services)

        assert result.media_path is None
        assert "Wie sagt man" in result.text_response


class TestVisualVocabularyWordSelection:
    def test_prefers_articled_entries_first(self):
        entries = [
            {"source_text": "quickly", "translated_text": "schnell"},
            {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
        ]
        services, _pool = make_services(entries, sd_client=None)
        module = VisualVocabulary()

        module.start(services)

        assert module._current["translated_text"] == "Hund"
        assert [e["translated_text"] for e in module._queue] == ["schnell"]


class TestVisualVocabularyResults:
    def test_complete_reports_images_generated_and_accuracy(self):
        sd_client = FakeSDClient(
            reachable=True, image_path_by_prompt={HUND_PROMPT: "/tmp/de_hund.png"})
        services, _pool = make_services([HUND_ENTRY], sd_client=sd_client)
        module = VisualVocabulary()
        module.start(services)
        module.handle_response("Hund", services)

        results = module.complete(services)

        assert results["images_generated"] == 1
        assert results["accuracy"] == 1.0
        assert results["new_words"] == ["Hund"]
        assert results["words_reviewed"] == ["Hund"]
