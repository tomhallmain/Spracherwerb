"""Tests for IdiomsAndExpressions: a few idioms + one ungraded practice turn."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.idioms_and_expressions import IdiomsAndExpressions
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


IDIOMS_TEXT = (
    "IDIOM 1: die Daumen drücken - literally 'press the thumbs', figuratively "
    "'wish someone luck'. Similar to English 'fingers crossed'. Example: Ich "
    "drücke dir die Daumen für die Prüfung!\n"
    "IDIOM 2: ins Gras beißen - literally 'bite the grass', figuratively 'to "
    "die'. Similar to English 'bite the dust'. Example: Der alte Fernseher "
    "hat endlich ins Gras gebissen.\n"
    "IDIOM 3: die Kirsche auf der Sahne - literally 'the cherry on the "
    "cream', figuratively 'the best part'. Similar to English 'the cherry "
    "on top'. Example: Das war die Kirsche auf der Sahne des Abends."
)


class TestIdiomsAndExpressionsRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(IdiomsAndExpressions)
        assert ActivityRegistry.is_implemented(ActivityType.IDIOMS_AND_EXPRESSIONS)
        module = ActivityRegistry.create(ActivityType.IDIOMS_AND_EXPRESSIONS)
        assert isinstance(module, IdiomsAndExpressions)


class TestIdiomsAndExpressionsStart:
    def test_presents_the_idioms_and_invites_practice(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT])
        services = make_services(llm)
        module = IdiomsAndExpressions()

        result = module.start(services)

        assert "die Daumen drücken" in result.text_response
        assert "done" in result.text_response.lower() or "fertig" in result.text_response.lower()
        assert result.expects_response is True

    def test_parses_idiom_titles(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT])
        services = make_services(llm)
        module = IdiomsAndExpressions()

        module.start(services)

        assert module._idioms_studied == [
            "die Daumen drücken", "ins Gras beißen", "die Kirsche auf der Sahne",
        ]

    def test_malformed_response_still_shows_text_with_no_parsed_idioms(self):
        llm = FakeLLM(responses=["Just some idioms with no markers at all."])
        services = make_services(llm)
        module = IdiomsAndExpressions()

        result = module.start(services)

        assert "Just some idioms with no markers at all." in result.text_response
        assert module._idioms_studied == []

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = IdiomsAndExpressions()

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
        module = IdiomsAndExpressions()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []


class TestIdiomsAndExpressionsPractice:
    def test_saying_done_completes_without_another_llm_call(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT])
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)

        result = module.handle_response("done", services)

        assert result.is_complete is True
        assert len(llm.calls) == 1  # only the intro call

    def test_practice_attempt_gets_encouraging_feedback(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT, "Schöner Versuch, gut gemacht!"])
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)

        result = module.handle_response("Ich drücke dir die Daumen!", services)

        assert result.is_complete is True
        assert result.text_response == "Schöner Versuch, gut gemacht!"

    def test_feedback_call_never_asks_for_a_grade(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT, "Nice one!"])
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)

        module.handle_response("Ich drücke dir die Daumen!", services)

        feedback_query = llm.calls[1]['query']
        assert "right or wrong" in feedback_query.lower()

    def test_feedback_failure_falls_back_to_a_canned_message(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT], fail_after=1)
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)

        result = module.handle_response("Ich drücke dir die Daumen!", services)

        assert result.is_complete is True
        assert "Nice try!" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT])
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)
        module.handle_response("done", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestIdiomsAndExpressionsResults:
    def test_complete_reports_idioms_studied_only(self):
        llm = FakeLLM(responses=[IDIOMS_TEXT])
        services = make_services(llm)
        module = IdiomsAndExpressions()
        module.start(services)
        module.handle_response("done", services)

        results = module.complete(services)

        assert results == {
            "idioms_studied": [
                "die Daumen drücken", "ins Gras beißen", "die Kirsche auf der Sahne",
            ],
        }
        assert "quiz_score" not in results
