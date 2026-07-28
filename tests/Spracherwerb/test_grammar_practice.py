"""Tests for GrammarPractice: LLM-driven topic explanation + graded exercises."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.grammar_practice import EXERCISES_PER_SESSION, GrammarPractice, _TOPICS_BY_LEVEL
from Spracherwerb.learning_memory import LearningMemory
from Spracherwerb.session_config import SessionConfig


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture(autouse=True)
def clean_learning_memory():
    before = dict(LearningMemory.grammar_points_covered)
    LearningMemory.grammar_points_covered = {}
    yield
    LearningMemory.grammar_points_covered = before


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


def make_services(llm, proficiency_level="intermediate", target_language="de", source_language="en",
                   word_reference=None, vocabulary_pool=None):
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
        word_reference=word_reference,
        vocabulary_pool=vocabulary_pool,
    )


LESSON = (
    "EXPLANATION: Das Perfekt wird mit haben oder sein gebildet.\n"
    "EXERCISE 1: Ich ___ (gehen) gestern ins Kino.\n"
    "EXERCISE 2: Er ___ (essen) eine Pizza.\n"
    "EXERCISE 3: Wir ___ (spielen) Fußball."
)


class TestGrammarPracticeRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(GrammarPractice)
        assert ActivityRegistry.is_implemented(ActivityType.GRAMMAR_PRACTICE)
        module = ActivityRegistry.create(ActivityType.GRAMMAR_PRACTICE)
        assert isinstance(module, GrammarPractice)


class TestGrammarPracticeStart:
    def test_returns_explanation_and_first_exercise_only(self):
        llm = FakeLLM(responses=[LESSON])
        services = make_services(llm)
        module = GrammarPractice()

        result = module.start(services)

        assert "Das Perfekt wird mit haben oder sein gebildet." in result.text_response
        assert "Ich ___ (gehen) gestern ins Kino." in result.text_response
        assert "Er ___ (essen) eine Pizza." not in result.text_response

    def test_picks_the_first_topic_for_the_proficiency_level(self):
        llm = FakeLLM(responses=[LESSON])
        services = make_services(llm, proficiency_level="beginner")
        module = GrammarPractice()

        module.start(services)

        assert module._topic == _TOPICS_BY_LEVEL["beginner"][0]

    def test_unknown_proficiency_falls_back_to_intermediate_topics(self):
        llm = FakeLLM(responses=[LESSON])
        services = make_services(llm, proficiency_level="expert")
        module = GrammarPractice()

        module.start(services)

        assert module._topic == _TOPICS_BY_LEVEL["intermediate"][0]

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = GrammarPractice()

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
        module = GrammarPractice()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []

    def test_malformed_response_falls_back_to_a_generic_exercise(self):
        llm = FakeLLM(responses=["Just an explanation with no exercise markers."])
        services = make_services(llm)
        module = GrammarPractice()

        result = module.start(services)

        assert "Use today's grammar point in a sentence of your own." in result.text_response

    def test_includes_the_vocabulary_hint_when_the_dictionary_has_one(self):
        llm = FakeLLM(responses=[LESSON])
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        word_reference = FakeWordReference(results_by_word={
            "dog": FakeDictionaryResult([FakeDictionarySection([FakeDictionaryEntry(to_pos="noun")])]),
        })
        services = make_services(llm, word_reference=word_reference, vocabulary_pool=pool)
        module = GrammarPractice()

        module.start(services)

        assert "Hund (noun)" in llm.calls[0]['query']


class TestGrammarPracticeExercises:
    def test_runs_all_exercises_and_completes(self):
        llm = FakeLLM(responses=[
            LESSON,
            "CORRECT\nGut gemacht!",
            "CORRECT\nGenau!",
            "CORRECT\nSehr gut!",
        ])
        services = make_services(llm)
        module = GrammarPractice()
        module.start(services)

        results = [module.handle_response(f"answer {i}", services) for i in range(EXERCISES_PER_SESSION)]

        assert [r.is_complete for r in results] == [False, False, True]
        assert "Session complete" in results[-1].text_response or "Sitzung abgeschlossen" in results[-1].text_response

    def test_incorrect_answer_is_recorded_as_an_error(self):
        llm = FakeLLM(responses=[LESSON, "INCORRECT\nNicht ganz richtig."])
        services = make_services(llm)
        module = GrammarPractice()
        module.start(services)

        module.handle_response("wrong answer", services)

        assert module._errors == ["wrong answer"]

    def test_grading_failure_still_advances(self):
        llm = FakeLLM(responses=[LESSON], fail_after=1)
        services = make_services(llm)
        module = GrammarPractice()
        module.start(services)

        result = module.handle_response("an answer", services)

        assert "Could not check that answer right now" in result.text_response
        assert result.is_complete is False

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=[
            LESSON, "CORRECT\n1", "CORRECT\n2", "CORRECT\n3",
        ])
        services = make_services(llm)
        module = GrammarPractice()
        module.start(services)
        for i in range(EXERCISES_PER_SESSION):
            module.handle_response(f"answer {i}", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestGrammarPracticeResults:
    def test_complete_reports_shape_and_updates_learning_memory(self):
        llm = FakeLLM(responses=[LESSON, "CORRECT\n1", "INCORRECT\n2", "CORRECT\n3"])
        services = make_services(llm)
        module = GrammarPractice()
        module.start(services)
        for i in range(EXERCISES_PER_SESSION):
            module.handle_response(f"answer {i}", services)

        results = module.complete(services)

        assert results["grammar_points"] == [module._topic]
        assert results["exercises_completed"] == EXERCISES_PER_SESSION
        assert results["errors"] == ["answer 1"]
        assert module._topic in LearningMemory.grammar_points_covered["de"]
