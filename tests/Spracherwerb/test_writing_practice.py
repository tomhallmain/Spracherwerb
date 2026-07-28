"""Tests for WritingPractice: one submission graded by LanguageTool + LLM."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.writing_practice import WritingPractice


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


class FakeLanguageError:
    def __init__(self, message, short_message="", replacements=None, rule_category=""):
        self.message = message
        self.short_message = short_message
        self.replacements = replacements or []
        self.rule_category = rule_category


class FakeLanguageTool:
    def __init__(self, errors=None, fail=False):
        self._errors = errors if errors is not None else []
        self._fail = fail
        self.calls = []

    def check_text(self, text, language):
        self.calls.append((text, language))
        if self._fail:
            raise Exception("LanguageTool unavailable")
        return list(self._errors)


class FakeDictionaryEntry:
    def __init__(self, to_pos=None, from_pos=None):
        self.to_pos = to_pos
        self.from_pos = from_pos


class FakeDictionarySection:
    def __init__(self, entries):
        self.entries = entries


class FakeDictionaryResult:
    def __init__(self, sections):
        self.sections = sections


class FakeVocabularyPool:
    def __init__(self, entries):
        self._entries = entries

    def get_review_candidates(self, source_language, target_language, limit=5):
        return list(self._entries[:limit])


class FakeWordReference:
    def __init__(self, results_by_word=None):
        self._results_by_word = results_by_word or {}

    def lookup(self, word, from_language, to_language):
        return self._results_by_word.get(word)


def make_services(llm, language_tool=None, proficiency_level="intermediate", target_language="de",
                   source_language="en", word_reference=None, vocabulary_pool=None):
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
        language_tool=language_tool,
        word_reference=word_reference,
        vocabulary_pool=vocabulary_pool,
    )


class TestWritingPracticeRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(WritingPractice)
        assert ActivityRegistry.is_implemented(ActivityType.WRITING_PRACTICE)
        module = ActivityRegistry.create(ActivityType.WRITING_PRACTICE)
        assert isinstance(module, WritingPractice)


class TestWritingPracticeStart:
    def test_returns_the_llm_prompt(self):
        llm = FakeLLM(responses=["Schreib ein paar Sätze über dein Wochenende."])
        services = make_services(llm)
        module = WritingPractice()

        result = module.start(services)

        assert result.text_response == "Schreib ein paar Sätze über dein Wochenende."
        assert result.expects_response is True

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = WritingPractice()

        result = module.start(services)

        assert result.expects_response is False
        assert "isn't available" in result.text_response.lower()

    def test_missing_activity_prompt_degrades_gracefully(self):
        class FailingPrompter:
            def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
                raise FileNotFoundError("prompt file missing")

        llm = FakeLLM(responses=["should not be reached"])
        services = make_services(llm)
        services.prompter = FailingPrompter()
        module = WritingPractice()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []

    def test_includes_the_vocabulary_hint_when_the_dictionary_has_one(self):
        llm = FakeLLM(responses=["Schreib etwas."])
        pool = FakeVocabularyPool([{"source_text": "bicycle", "translated_text": "Fahrrad"}])
        word_reference = FakeWordReference(results_by_word={
            "bicycle": FakeDictionaryResult([FakeDictionarySection([FakeDictionaryEntry(to_pos="noun")])]),
        })
        services = make_services(llm, word_reference=word_reference, vocabulary_pool=pool)
        module = WritingPractice()

        module.start(services)

        assert "Fahrrad (noun)" in llm.calls[0]['query']


class TestWritingPracticeGrading:
    def test_shows_language_tool_corrections_and_llm_feedback(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Guter Versuch, weiter so!"])
        language_tool = FakeLanguageTool(errors=[
            FakeLanguageError(
                "Missing verb agreement", short_message="Verb agreement",
                replacements=["gehe", "gehst"], rule_category="GRAMMAR"),
        ])
        services = make_services(llm, language_tool=language_tool)
        module = WritingPractice()
        module.start(services)

        result = module.handle_response("Ich geht ins Kino.", services)

        assert "Corrections:" in result.text_response
        assert "Verb agreement" in result.text_response
        assert "gehe, gehst" in result.text_response
        assert "Guter Versuch, weiter so!" in result.text_response
        assert result.is_complete is True

    def test_records_corrections_and_grammar_tags(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Feedback."])
        language_tool = FakeLanguageTool(errors=[
            FakeLanguageError("Missing verb agreement", rule_category="GRAMMAR"),
            FakeLanguageError("Wrong article", rule_category="GRAMMAR"),
            FakeLanguageError("Style suggestion", rule_category="STYLE"),
        ])
        services = make_services(llm, language_tool=language_tool)
        module = WritingPractice()
        module.start(services)

        module.handle_response("some text", services)

        results = module.complete(services)
        assert results["corrections"] == ["Missing verb agreement", "Wrong article", "Style suggestion"]
        assert results["grammar_tags"] == ["GRAMMAR", "STYLE"]

    def test_no_language_tool_service_falls_back_to_llm_only(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Nice sentences overall!"])
        services = make_services(llm, language_tool=None)
        module = WritingPractice()
        module.start(services)

        result = module.handle_response("some text", services)

        assert "Corrections:" not in result.text_response
        assert result.text_response == "Nice sentences overall!"

    def test_language_tool_failure_falls_back_to_llm_only(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Nice sentences overall!"])
        language_tool = FakeLanguageTool(fail=True)
        services = make_services(llm, language_tool=language_tool)
        module = WritingPractice()
        module.start(services)

        result = module.handle_response("some text", services)

        assert "Corrections:" not in result.text_response
        assert result.text_response == "Nice sentences overall!"

    def test_no_errors_and_no_llm_feedback_shows_default_message(self):
        llm = FakeLLM(responses=["Schreib etwas."], fail_after=1)
        services = make_services(llm, language_tool=None)
        module = WritingPractice()
        module.start(services)

        result = module.handle_response("some text", services)

        assert result.text_response == "Nice work -- no issues found!"

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Feedback."])
        services = make_services(llm)
        module = WritingPractice()
        module.start(services)
        module.handle_response("some text", services)

        result = module.handle_response("more text", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestWritingPracticeResults:
    def test_complete_reports_the_submission(self):
        llm = FakeLLM(responses=["Schreib etwas.", "Feedback."])
        services = make_services(llm)
        module = WritingPractice()
        module.start(services)
        module.handle_response("Ich gehe ins Kino.", services)

        results = module.complete(services)

        assert results["submissions"] == ["Ich gehe ins Kino."]

    def test_complete_before_any_submission_reports_empty(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = WritingPractice()
        module.start(services)

        results = module.complete(services)

        assert results == {"submissions": [], "corrections": [], "grammar_tags": []}
