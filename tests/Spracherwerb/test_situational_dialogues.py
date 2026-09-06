"""Tests for SituationalDialogues: goal-oriented LLM role-play."""

import pytest

from Spracherwerb import situational_dialogues
from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.media_generation import MediaGenerationService
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.situational_dialogues import GOAL_MARKER, MAX_TURNS, SituationalDialogues


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture(autouse=True)
def deterministic_scenario(monkeypatch):
    """Pin scenario selection to the first built-in scenario for predictable tests."""
    monkeypatch.setattr(situational_dialogues.random, "choice", lambda seq: seq[0])


@pytest.fixture(autouse=True)
def isolated_image_cache(tmp_path, monkeypatch):
    """Redirect the module's image cache dir so tests never touch the real cache/ tree."""
    monkeypatch.setattr(situational_dialogues, "IMAGE_CACHE_DIR", tmp_path / "situational_dialogues")


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


class FakeSDClient:
    def __init__(self, reachable=True, image_path=None):
        self._reachable = reachable
        self._image_path = image_path
        self.generate_calls = []

    def is_reachable(self):
        return self._reachable

    def generate_image(self, positive_prompt, target_dir, filename, **kwargs):
        self.generate_calls.append((positive_prompt, target_dir, filename))
        return self._image_path


#: Services built during a test, shut down by the autouse fixture below.
_media_services = []


@pytest.fixture(autouse=True)
def shutdown_media_services():
    """Stop each test's generation worker; they are daemon threads otherwise
    left running for the rest of the session."""
    yield
    while _media_services:
        _media_services.pop().shutdown()


def make_services(llm, sd_client=None, proficiency_level="intermediate", target_language="de",
                   source_language="en"):
    session_config = SessionConfig({
        "source_language": source_language,
        "target_language": target_language,
        "proficiency_level": proficiency_level,
    })
    media = None
    if sd_client is not None:
        media = MediaGenerationService(sd_client=sd_client)
        _media_services.append(media)
    return ModuleServices(
        prompter=FakePrompter(),
        voice=None,
        session_config=session_config,
        session_context=None,
        llm=llm,
        sd_client=sd_client,
        media=media,
    )


class TestSituationalDialoguesRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(SituationalDialogues)
        assert ActivityRegistry.is_implemented(ActivityType.SITUATIONAL_DIALOGUES)
        module = ActivityRegistry.create(ActivityType.SITUATIONAL_DIALOGUES)
        assert isinstance(module, SituationalDialogues)


class TestSituationalDialoguesStart:
    def test_returns_the_scenario_intro_and_opening_line(self):
        llm = FakeLLM(responses=["Guten Tag! Wohin möchten Sie reisen?"])
        services = make_services(llm)
        module = SituationalDialogues()

        result = module.start(services)

        assert "Buying a train ticket" in result.text_response
        assert "Guten Tag! Wohin möchten Sie reisen?" in result.text_response
        assert result.expects_response is True

    def test_system_prompt_includes_scenario_and_goal(self):
        llm = FakeLLM(responses=["Guten Tag!"])
        services = make_services(llm)
        module = SituationalDialogues()

        module.start(services)

        system_prompt = llm.calls[0]['system_prompt']
        assert "ticket agent" in system_prompt
        assert "destination" in system_prompt
        assert GOAL_MARKER in system_prompt

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        services = make_services(llm)
        module = SituationalDialogues()

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
        module = SituationalDialogues()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []

    def test_no_scene_image_when_sd_unavailable(self):
        llm = FakeLLM(responses=["Guten Tag!"])
        services = make_services(llm, sd_client=None)
        module = SituationalDialogues()

        result = module.start(services)

        assert result.media_path is None

    def test_scene_image_generated_when_sd_available(self):
        llm = FakeLLM(responses=["Guten Tag!"])
        sd_client = FakeSDClient(reachable=True, image_path="/tmp/scene.png")
        services = make_services(llm, sd_client=sd_client)
        module = SituationalDialogues()

        result = module.start(services)

        assert result.media_path == "/tmp/scene.png"
        assert len(sd_client.generate_calls) == 1


class TestSituationalDialoguesTurns:
    def test_continues_when_goal_not_yet_met(self):
        llm = FakeLLM(responses=["Guten Tag!", "Welche Stadt bitte?"])
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)

        result = module.handle_response("Ich möchte nach Berlin.", services)

        assert result.is_complete is False
        assert result.text_response == "Welche Stadt bitte?"

    def test_goal_marker_ends_the_session_and_is_stripped_from_the_reply(self):
        llm = FakeLLM(responses=[
            "Guten Tag!",
            f"Hier ist Ihr Ticket nach Berlin.\n{GOAL_MARKER}",
        ])
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)

        result = module.handle_response("Ein Ticket nach Berlin, bitte.", services)

        assert result.is_complete is True
        assert GOAL_MARKER not in result.text_response
        assert "Hier ist Ihr Ticket nach Berlin." in result.text_response
        assert "Goal achieved!" in result.text_response

    def test_ends_after_the_turn_limit(self):
        responses = ["Guten Tag!"] + [f"Antwort {i}" for i in range(MAX_TURNS)]
        llm = FakeLLM(responses=responses)
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)

        results = [module.handle_response(f"turn {i}", services) for i in range(MAX_TURNS)]

        assert [r.is_complete for r in results] == [False] * (MAX_TURNS - 1) + [True]

    def test_ends_early_on_a_farewell_word(self):
        llm = FakeLLM(responses=["Guten Tag!", "Auf Wiedersehen!"])
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)

        result = module.handle_response("Okay, bye!", services)

        assert result.is_complete is True

    def test_llm_failure_mid_dialogue_ends_gracefully(self):
        llm = FakeLLM(responses=["Guten Tag!"], fail_after=1)
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)

        result = module.handle_response("Ein Ticket, bitte.", services)

        assert result.is_complete is True
        assert "Lost the connection" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=["Guten Tag!", f"Bitte sehr.\n{GOAL_MARKER}"])
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)
        module.handle_response("Ein Ticket, bitte.", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestSituationalDialoguesResults:
    def test_complete_reports_goal_met(self):
        llm = FakeLLM(responses=["Guten Tag!", f"Bitte sehr.\n{GOAL_MARKER}"])
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)
        module.handle_response("Ein Ticket, bitte.", services)

        results = module.complete(services)

        assert results["scenario_id"] == "buy_train_ticket"
        assert results["goals_met"] == ["buy_train_ticket"]
        assert results["turns"] == 1

    def test_complete_reports_no_goal_met_on_turn_limit_exit(self):
        responses = ["Guten Tag!"] + [f"Antwort {i}" for i in range(MAX_TURNS)]
        llm = FakeLLM(responses=responses)
        services = make_services(llm)
        module = SituationalDialogues()
        module.start(services)
        for i in range(MAX_TURNS):
            module.handle_response(f"turn {i}", services)

        results = module.complete(services)

        assert results["goals_met"] == []
        assert results["turns"] == MAX_TURNS
