"""Tests for CulturalContext: an LLM cultural note + ungraded follow-up Q&A."""

import pytest

from Spracherwerb import cultural_context
from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.cultural_context import MAX_FOLLOW_UP_QUESTIONS, CulturalContext
from Spracherwerb.session_config import SessionConfig


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture(autouse=True)
def deterministic_topic(monkeypatch):
    """Pin topic selection to the first built-in topic for predictable tests."""
    monkeypatch.setattr(cultural_context.random, "choice", lambda seq: seq[0])


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


class TestCulturalContextRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(CulturalContext)
        assert ActivityRegistry.is_implemented(ActivityType.CULTURAL_CONTEXT)
        module = ActivityRegistry.create(ActivityType.CULTURAL_CONTEXT)
        assert isinstance(module, CulturalContext)


class TestCulturalContextStart:
    def test_presents_the_topic_and_invites_a_question(self):
        llm = FakeLLM(responses=["In Deutschland feiert man..."])
        services = make_services(llm)
        module = CulturalContext()

        result = module.start(services)

        assert "In Deutschland feiert man..." in result.text_response
        assert "done" in result.text_response.lower() or "fertig" in result.text_response.lower()
        assert result.expects_response is True

    def test_system_prompt_says_never_grade(self):
        llm = FakeLLM(responses=["Note."])
        services = make_services(llm)
        module = CulturalContext()

        module.start(services)

        system_prompt = llm.calls[0]['system_prompt']
        assert "never grade" in system_prompt.lower()

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = CulturalContext()

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
        module = CulturalContext()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []

    def test_includes_the_vocabulary_hint_when_the_dictionary_has_one(self):
        llm = FakeLLM(responses=["Note."])
        pool = FakeVocabularyPool([{"source_text": "bread", "translated_text": "Brot"}])
        word_reference = FakeWordReference(results_by_word={
            "bread": FakeDictionaryResult([FakeDictionarySection([FakeDictionaryEntry(to_pos="noun")])]),
        })
        services = make_services(llm, word_reference=word_reference, vocabulary_pool=pool)
        module = CulturalContext()

        module.start(services)

        assert "Brot (noun)" in llm.calls[0]['query']


class TestCulturalContextFollowUp:
    def test_continues_when_not_done(self):
        llm = FakeLLM(responses=["Note.", "More context."])
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)

        result = module.handle_response("Why is that?", services)

        assert result.is_complete is False
        assert "More context." in result.text_response

    def test_saying_done_ends_without_another_llm_call(self):
        llm = FakeLLM(responses=["Note."])
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)

        result = module.handle_response("done", services)

        assert result.is_complete is True
        assert len(llm.calls) == 1  # only the opening call, no follow-up call

    def test_ends_automatically_after_the_follow_up_cap(self):
        responses = ["Note."] + [f"Answer {i}" for i in range(MAX_FOLLOW_UP_QUESTIONS)]
        llm = FakeLLM(responses=responses)
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)

        results = [
            module.handle_response(f"question {i}", services)
            for i in range(MAX_FOLLOW_UP_QUESTIONS)
        ]

        assert [r.is_complete for r in results] == [False] * (MAX_FOLLOW_UP_QUESTIONS - 1) + [True]

    def test_llm_failure_mid_dialogue_ends_gracefully(self):
        llm = FakeLLM(responses=["Note."], fail_after=1)
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)

        result = module.handle_response("Why is that?", services)

        assert result.is_complete is True
        assert "Lost the connection" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=["Note."])
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)
        module.handle_response("done", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestCulturalContextResults:
    def test_complete_reports_topic_and_question_count(self):
        llm = FakeLLM(responses=["Note.", "More."])
        services = make_services(llm)
        module = CulturalContext()
        module.start(services)
        module.handle_response("Why?", services)

        results = module.complete(services)

        assert results["topics"] == [module._topic]
        assert results["questions_answered"] == 1
