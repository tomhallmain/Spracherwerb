"""Tests for ConversationPractice, the LLM-driven dialogue activity."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.conversation_practice import MAX_TURNS, ConversationPractice
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
    """Stand-in for extensions.llm.LLM."""

    def __init__(self, responses=None, fail=False, fail_after=None):
        self._responses = list(responses or [])
        self._fail = fail
        self._fail_after = fail_after
        self.calls = []

    def generate_response(self, query, timeout=180, context=None, system_prompt=None, **kwargs):
        self.calls.append({
            'query': query, 'system_prompt': system_prompt,
            'context': context, 'timeout': timeout,
        })
        if self._fail or (self._fail_after is not None and len(self.calls) > self._fail_after):
            raise Exception("LLM unavailable")
        if not self._responses:
            raise Exception("No more fake responses queued")
        response = self._responses.pop(0)
        return FakeLLMResult(response, context=(context or []) + [len(self.calls)])


class FakePrompter:
    def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
        return f"You are a tutor running a {prompt_name} activity."


def make_services(llm, proficiency_level="intermediate", target_language="de", source_language="en"):
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
    )


class TestConversationPracticeRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(ConversationPractice)
        assert ActivityRegistry.is_implemented(ActivityType.CONVERSATION_PRACTICE)
        module = ActivityRegistry.create(ActivityType.CONVERSATION_PRACTICE)
        assert isinstance(module, ConversationPractice)


class TestConversationPracticeStart:
    def test_returns_the_llm_opening_message(self):
        llm = FakeLLM(responses=["Hallo! Wie geht es dir heute?"])
        services = make_services(llm)
        module = ConversationPractice()

        result = module.start(services)

        assert result.text_response == "Hallo! Wie geht es dir heute?"
        assert result.expects_response is True

    def test_system_prompt_names_the_target_language_and_level(self):
        llm = FakeLLM(responses=["Hallo!"])
        services = make_services(llm, proficiency_level="beginner", target_language="de")
        module = ConversationPractice()

        module.start(services)

        system_prompt = llm.calls[0]['system_prompt']
        assert "German" in system_prompt
        assert "beginner" in system_prompt

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = ConversationPractice()

        result = module.start(services)

        assert result.expects_response is False
        assert "Der Gesprächspartner ist gerade nicht erreichbar." in result.text_response
        assert "isn't available" in result.text_response.lower()

    def test_missing_activity_prompt_degrades_gracefully(self):
        class FailingPrompter:
            def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
                raise FileNotFoundError("prompt file missing")

        llm = FakeLLM(responses=["should not be reached"])
        services = make_services(llm)
        services.prompter = FailingPrompter()
        module = ConversationPractice()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []


class TestConversationPracticeTurns:
    def test_continues_the_conversation_with_running_context(self):
        llm = FakeLLM(responses=["Hallo!", "Schön, das zu hören!"])
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)

        result = module.handle_response("Mir geht es gut, danke!", services)

        assert result.text_response == "Schön, das zu hören!"
        assert result.is_complete is False
        # No context yet on the opening call; the second call carries forward
        # whatever context the first call's LLMResult returned.
        assert llm.calls[0]['context'] is None
        assert llm.calls[1]['context'] == [1]

    def test_ends_after_the_turn_limit(self):
        responses = ["Hallo!"] + [f"Antwort {i}" for i in range(MAX_TURNS)]
        llm = FakeLLM(responses=responses)
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)

        results = [module.handle_response(f"turn {i}", services) for i in range(MAX_TURNS)]

        assert [r.is_complete for r in results] == [False] * (MAX_TURNS - 1) + [True]
        assert "Sitzung abgeschlossen" in results[-1].text_response

    def test_ends_early_on_a_farewell_word(self):
        llm = FakeLLM(responses=["Hallo!", "Tschüss, bis bald!"])
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)

        result = module.handle_response("Okay, bye!", services)

        assert result.is_complete is True
        assert "Sitzung abgeschlossen" in result.text_response

    def test_llm_failure_mid_conversation_ends_gracefully(self):
        llm = FakeLLM(responses=["Hallo!"], fail_after=1)
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)

        result = module.handle_response("Mir geht es gut!", services)

        assert result.is_complete is True
        assert "Lost the connection" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=["Hallo!", "Tschüss!"])
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)
        module.handle_response("bye", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestConversationPracticeResults:
    def test_complete_reports_turn_count(self):
        llm = FakeLLM(responses=["Hallo!", "Antwort"])
        services = make_services(llm)
        module = ConversationPractice()
        module.start(services)
        module.handle_response("Hi!", services)

        results = module.complete(services)

        assert results == {"turns": 1, "corrections": [], "new_vocab": []}
