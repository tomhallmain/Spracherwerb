"""Tests for ReadingComprehension: Gutenberg-or-LLM passage + graded questions."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.reading_comprehension import EXCERPT_TARGET_WORDS, ReadingComprehension
from Spracherwerb.session_config import SessionConfig


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


class FakeLLMResult:
    def __init__(self, response, context=None):
        self.response = response
        self.context = context


class FakeLLM:
    def __init__(self, responses=None, fail=False, fail_after=None):
        self._responses = list(responses or [])
        self._fail = fail
        self._fail_after = fail_after
        self.calls = []

    def generate_response(self, query, timeout=180, context=None, system_prompt=None, **kwargs):
        self.calls.append({'query': query, 'system_prompt': system_prompt, 'context': context})
        if self._fail or (self._fail_after is not None and len(self.calls) > self._fail_after):
            raise Exception("LLM unavailable")
        if not self._responses:
            raise Exception("No more fake responses queued")
        return FakeLLMResult(self._responses.pop(0), context=(context or []) + [len(self.calls)])


class FakePrompter:
    def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
        return f"You are a tutor running a {prompt_name} activity."


class FakeGutenbergBook:
    def __init__(self, book_id):
        self.id = book_id


class FakeGutenberg:
    def __init__(self, books=None, texts_by_id=None, fail_search=False, fail_text_for=None):
        self._books = books or []
        self._texts_by_id = texts_by_id or {}
        self._fail_search = fail_search
        self._fail_text_for = fail_text_for or set()

    def get_popular_books(self, language, limit=5):
        if self._fail_search:
            raise Exception("network error")
        return list(self._books[:limit])

    def get_book_text(self, book_id):
        if book_id in self._fail_text_for:
            raise Exception("network error")
        return self._texts_by_id.get(book_id)


class FakeDataManager:
    def __init__(self, fail=False):
        self.added = []
        self._fail = fail

    def add_translation(self, translation):
        if self._fail:
            raise Exception("save failed")
        self.added.append(translation)
        return True


class FakeVocabularyPool:
    def __init__(self, data_manager):
        self.data_manager = data_manager


def make_services(llm, gutenberg=None, vocabulary_pool=None, proficiency_level="intermediate",
                   target_language="de", source_language="en"):
    session_config = SessionConfig({
        "source_language": source_language,
        "target_language": target_language,
        "proficiency_level": proficiency_level,
    })
    return ModuleServices(
        prompter=FakePrompter(),
        voice=None,
        session_config=session_config,
        session_context=None,
        llm=llm,
        gutenberg=gutenberg,
        vocabulary_pool=vocabulary_pool,
    )


def gutenberg_text(word_count):
    body = " ".join(["wort"] * word_count)
    return (
        "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
        f"{body}\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***"
    )


PASSAGE_TEXT = "Das ist ein kurzer Text über den Alltag in Deutschland."
QUESTIONS_TEXT = (
    "QUESTION 1: Worum geht es im Text?\n"
    "QUESTION 2: Wo spielt der Text?\n"
    "QUESTION 3: Was ist das Thema?"
)


class TestReadingComprehensionRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(ReadingComprehension)
        assert ActivityRegistry.is_implemented(ActivityType.READING_COMPREHENSION)
        module = ActivityRegistry.create(ActivityType.READING_COMPREHENSION)
        assert isinstance(module, ReadingComprehension)


class TestReadingComprehensionPassageSourcing:
    def test_uses_llm_passage_when_no_gutenberg_service(self):
        llm = FakeLLM(responses=[PASSAGE_TEXT, QUESTIONS_TEXT])
        services = make_services(llm, gutenberg=None)
        module = ReadingComprehension()

        result = module.start(services)

        assert module._passage_id == "llm-generated"
        assert PASSAGE_TEXT in result.text_response
        assert len(llm.calls) == 2

    def test_uses_gutenberg_excerpt_and_skips_llm_passage_generation(self):
        text = gutenberg_text(EXCERPT_TARGET_WORDS + 20)
        gutenberg = FakeGutenberg(books=[FakeGutenbergBook(42)], texts_by_id={42: text})
        llm = FakeLLM(responses=[QUESTIONS_TEXT])
        services = make_services(llm, gutenberg=gutenberg)
        module = ReadingComprehension()

        result = module.start(services)

        assert module._passage_id == "gutenberg:42"
        assert "wort" in result.text_response
        assert len(llm.calls) == 1  # only the questions call

    def test_falls_back_to_llm_when_gutenberg_excerpt_too_short(self):
        text = gutenberg_text(10)  # well under EXCERPT_TARGET_WORDS
        gutenberg = FakeGutenberg(books=[FakeGutenbergBook(1)], texts_by_id={1: text})
        llm = FakeLLM(responses=[PASSAGE_TEXT, QUESTIONS_TEXT])
        services = make_services(llm, gutenberg=gutenberg)
        module = ReadingComprehension()

        module.start(services)

        assert module._passage_id == "llm-generated"

    def test_falls_back_to_llm_when_gutenberg_search_fails(self):
        gutenberg = FakeGutenberg(fail_search=True)
        llm = FakeLLM(responses=[PASSAGE_TEXT, QUESTIONS_TEXT])
        services = make_services(llm, gutenberg=gutenberg)
        module = ReadingComprehension()

        module.start(services)

        assert module._passage_id == "llm-generated"

    def test_tries_the_next_book_when_a_text_fetch_fails(self):
        text = gutenberg_text(EXCERPT_TARGET_WORDS + 20)
        gutenberg = FakeGutenberg(
            books=[FakeGutenbergBook(1), FakeGutenbergBook(2)],
            texts_by_id={2: text},
            fail_text_for={1},
        )
        llm = FakeLLM(responses=[QUESTIONS_TEXT])
        services = make_services(llm, gutenberg=gutenberg)
        module = ReadingComprehension()

        module.start(services)

        assert module._passage_id == "gutenberg:2"


class TestReadingComprehensionStart:
    def test_unavailable_when_nothing_produces_a_passage(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = ReadingComprehension()

        result = module.start(services)

        assert result.expects_response is False
        assert "isn't available" in result.text_response.lower() or "not available" in result.text_response.lower() or "no reading passage" in result.text_response.lower()

    def test_missing_activity_prompt_degrades_gracefully(self):
        class FailingPrompter:
            def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
                raise FileNotFoundError("prompt file missing")

        llm = FakeLLM(responses=["should not be reached"])
        services = make_services(llm)
        services.prompter = FailingPrompter()
        module = ReadingComprehension()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []


class TestReadingComprehensionQuestions:
    def test_runs_three_questions_then_asks_about_an_unknown_word(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ])
        services = make_services(llm)
        module = ReadingComprehension()
        module.start(services)

        results = [module.handle_response(f"answer {i}", services) for i in range(3)]

        assert [r.is_complete for r in results] == [False, False, False]
        last_text = results[-1].text_response.lower()
        assert "understand" in last_text or "verstanden" in last_text

    def test_saying_no_to_the_unknown_word_prompt_completes_cleanly(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ])
        services = make_services(llm)
        module = ReadingComprehension()
        module.start(services)
        for i in range(3):
            module.handle_response(f"answer {i}", services)

        result = module.handle_response("no", services)

        assert result.is_complete is True

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ])
        services = make_services(llm)
        module = ReadingComprehension()
        module.start(services)
        for i in range(3):
            module.handle_response(f"answer {i}", services)
        module.handle_response("no", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestReadingComprehensionUnknownWord:
    def test_flagged_word_is_translated_and_saved(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
            "everyday life",
        ])
        data_manager = FakeDataManager()
        pool = FakeVocabularyPool(data_manager)
        services = make_services(llm, vocabulary_pool=pool)
        module = ReadingComprehension()
        module.start(services)
        for i in range(3):
            module.handle_response(f"answer {i}", services)

        result = module.handle_response("Alltag", services)

        assert result.is_complete is True
        assert "everyday life" in result.text_response
        assert data_manager.added == [{
            'source_text': 'everyday life',
            'translated_text': 'Alltag',
            'source_language': 'en',
            'target_language': 'de',
            'notes': 'Added from reading comprehension',
        }]

    def test_translation_failure_still_completes_gracefully(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ], fail_after=5)
        services = make_services(llm)
        module = ReadingComprehension()
        module.start(services)
        for i in range(3):
            module.handle_response(f"answer {i}", services)

        result = module.handle_response("Alltag", services)

        assert result.is_complete is True
        assert "Could not translate" in result.text_response
        assert "Alltag" in module._new_words


class TestReadingComprehensionResults:
    def test_complete_reports_shape(self):
        llm = FakeLLM(responses=[
            PASSAGE_TEXT, QUESTIONS_TEXT,
            "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ])
        services = make_services(llm)
        module = ReadingComprehension()
        module.start(services)
        for i in range(3):
            module.handle_response(f"answer {i}", services)
        module.handle_response("no", services)

        results = module.complete(services)

        assert results["passage_id"] == "llm-generated"
        assert results["questions_answered"] == 3
        assert results["new_words"] == []
