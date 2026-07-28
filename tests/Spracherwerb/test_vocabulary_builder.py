"""Tests for VocabularyBuilder, the first real activity module."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.learning_memory import LearningMemory
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.vocabulary_builder import VocabularyBuilder


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


class FakeVocabularyPool:
    """Stand-in for utils.vocabulary_pool.VocabularyPool that skips TranslationDataManager."""

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


def make_services(entries, proficiency_level="intermediate", source_language="en",
                   target_language="de"):
    pool = FakeVocabularyPool(entries)
    session_config = SessionConfig({
        "source_language": source_language,
        "target_language": target_language,
        "proficiency_level": proficiency_level,
    })
    services = ModuleServices(
        prompter=None,
        voice=None,
        session_config=session_config,
        session_context=None,
        vocabulary_pool=pool,
    )
    return services, pool


FIVE_ENTRIES = [
    {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
    {"source_text": "cat", "translated_text": "Katze", "target_article": "die"},
    {"source_text": "house", "translated_text": "Haus", "target_article": "das"},
    {"source_text": "to go, to walk", "translated_text": "gehen"},
    {"source_text": "quickly", "translated_text": "schnell"},
]


class TestVocabularyBuilderRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(VocabularyBuilder)
        assert ActivityRegistry.is_implemented(ActivityType.VOCABULARY_BUILDER)
        module = ActivityRegistry.create(ActivityType.VOCABULARY_BUILDER)
        assert isinstance(module, VocabularyBuilder)


class TestVocabularyBuilderEmptyPool:
    def test_start_with_no_candidates_does_not_expect_a_response(self):
        services, _pool = make_services([])
        module = VocabularyBuilder()

        result = module.start(services)

        assert result.expects_response is False
        assert "no saved vocabulary" in result.text_response.lower()


class TestVocabularyBuilderDirection:
    def test_beginner_is_shown_the_target_word(self):
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries, proficiency_level="beginner")
        module = VocabularyBuilder()

        result = module.start(services)

        assert result.text_response == (
            'Was bedeutet „der Hund“? (What does "der Hund" mean?)'
        )

    def test_intermediate_is_shown_the_source_word(self):
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries, proficiency_level="intermediate")
        module = VocabularyBuilder()

        result = module.start(services)

        assert result.text_response == (
            'Wie sagt man „dog“ auf Deutsch? (Translate to German: dog)'
        )

    def test_unlisted_target_language_falls_back_to_english_only(self):
        entries = [{"source_text": "dog", "translated_text": "canis"}]
        services, _pool = make_services(entries, target_language="la")
        module = VocabularyBuilder()

        result = module.start(services)

        assert result.text_response == "Translate to Latin: dog"


class TestVocabularyBuilderTurnLoop:
    def test_runs_five_turns_and_completes_on_the_last_word(self):
        services, _pool = make_services(FIVE_ENTRIES)
        module = VocabularyBuilder()
        module.start(services)

        answers = ["Hund", "Katze", "Haus", "gehen", "schnell"]
        results = [module.handle_response(a, services) for a in answers]

        assert [r.is_complete for r in results] == [False, False, False, False, True]
        assert all("(Correct!)" in r.text_response for r in results)
        # Feedback and the next question are separated by a blank line, not run together.
        assert all("\n\n" in r.text_response for r in results[:-1])

    def test_wrong_answer_reveals_the_expected_word_and_still_advances(self):
        services, _pool = make_services(FIVE_ENTRIES)
        module = VocabularyBuilder()
        module.start(services)

        result = module.handle_response("nope", services)

        assert "der Hund" in result.text_response
        assert result.is_complete is False

    def test_accepts_the_bare_word_without_the_article(self):
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)

        result = module.handle_response("hund", services)

        assert "(Correct!)" in result.text_response

    def test_accepts_any_comma_separated_gloss_in_recall_source_direction(self):
        entries = [{"source_text": "to go, to walk", "translated_text": "gehen"}]
        services, _pool = make_services(entries, proficiency_level="beginner")
        module = VocabularyBuilder()
        module.start(services)

        result = module.handle_response("to walk", services)

        assert "(Correct!)" in result.text_response

    def test_handle_response_after_completion_says_so_without_crashing(self):
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)
        module.handle_response("Hund", services)

        result = module.handle_response("anything", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestVocabularyBuilderBilingualPhrasing:
    def test_incorrect_feedback_is_bilingual(self):
        # Two entries so the wrong answer doesn't also end the session and
        # append the session-complete summary onto the same message.
        entries = [
            {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
            {"source_text": "cat", "translated_text": "Katze", "target_article": "die"},
        ]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)

        result = module.handle_response("nope", services)

        feedback, _next_prompt = result.text_response.split("\n\n", 1)
        assert feedback == (
            'Nicht ganz -- die Antwort war „der Hund“. '
            '(Not quite -- the answer was "der Hund".)'
        )
        assert result.is_complete is False

    def test_session_complete_summary_is_bilingual(self):
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)

        result = module.handle_response("Hund", services)

        assert result.text_response == (
            'Richtig! (Correct!)\n\n'
            'Sitzung abgeschlossen: 1 von 1 richtig. '
            '(Session complete -- reviewed 1 word(s), 1 correct.)'
        )


class TestVocabularyBuilderResults:
    def test_complete_reports_accuracy_and_word_lists(self):
        entries = [
            {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
            {"source_text": "cat", "translated_text": "Katze", "target_article": "die"},
        ]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)
        module.handle_response("Hund", services)   # correct
        module.handle_response("wrong", services)  # incorrect

        results = module.complete(services)

        assert results["accuracy"] == 0.5
        assert set(results["new_words"]) == {"Hund", "Katze"}
        assert results["reviewed_words"] == []

    def test_words_already_in_learning_memory_count_as_reviewed_not_new(self):
        LearningMemory.vocabulary_learned["de"] = ["Hund"]
        entries = [{"source_text": "dog", "translated_text": "Hund", "target_article": "der"}]
        services, _pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)
        module.handle_response("Hund", services)

        results = module.complete(services)

        assert results["new_words"] == []
        assert results["reviewed_words"] == ["Hund"]

    def test_records_outcomes_via_vocabulary_pool(self):
        entries = [
            {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
            {"source_text": "cat", "translated_text": "Katze", "target_article": "die"},
        ]
        services, pool = make_services(entries)
        module = VocabularyBuilder()
        module.start(services)
        module.handle_response("Hund", services)
        module.handle_response("wrong", services)

        assert pool.recorded == [
            ("de", "Hund", "correct"),
            ("de", "Katze", "reviewed"),
        ]
