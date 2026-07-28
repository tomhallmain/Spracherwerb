"""Tests for ListeningComprehension, the audio-first passage+question activity."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.listening_comprehension import ListeningComprehension
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


class FakeVoice:
    def __init__(self, path="/tmp/passage.mp3"):
        self._path = path
        self.speed_calls = []
        self.speech_calls = []

    def set_speed(self, speed):
        self.speed_calls.append(speed)

    def generate_speech(self, text, topic="learning"):
        self.speech_calls.append(text)
        return self._path


class FakePrompter:
    def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
        return f"You are a tutor running a {prompt_name} activity."


def make_services(llm, voice, proficiency_level="intermediate", target_language="de",
                   source_language="en"):
    session_config = SessionConfig({
        "source_language": source_language,
        "target_language": target_language,
        "proficiency_level": proficiency_level,
    })
    return ModuleServices(
        prompter=FakePrompter(),
        voice=voice,
        session_config=session_config,
        session_context=None,
        llm=llm,
    )


PASSAGE_AND_QUESTION = "Das ist ein kurzer Text über den Alltag.\nQUESTION: Worum geht es im Text?"


class TestListeningComprehensionRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(ListeningComprehension)
        assert ActivityRegistry.is_implemented(ActivityType.LISTENING_COMPREHENSION)
        module = ActivityRegistry.create(ActivityType.LISTENING_COMPREHENSION)
        assert isinstance(module, ListeningComprehension)


class TestListeningComprehensionStart:
    def test_hides_the_passage_and_gives_voice_audio_when_tts_available(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION])
        voice = FakeVoice(path="/tmp/passage.mp3")
        services = make_services(llm, voice)
        module = ListeningComprehension()

        result = module.start(services)

        assert result.voice_response == "/tmp/passage.mp3"
        assert "Das ist ein kurzer Text" not in result.text_response
        assert "Worum geht es im Text?" in result.text_response

    def test_shows_the_passage_as_text_when_tts_unavailable(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION])
        voice = FakeVoice(path=None)
        services = make_services(llm, voice)
        module = ListeningComprehension()

        result = module.start(services)

        assert result.voice_response is None
        assert "Das ist ein kurzer Text" in result.text_response
        assert "Worum geht es im Text?" in result.text_response

    def test_sets_voice_speed_from_proficiency(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION])
        voice = FakeVoice()
        services = make_services(llm, voice, proficiency_level="beginner")
        module = ListeningComprehension()

        module.start(services)

        assert voice.speed_calls == [0.85]

    def test_unavailable_llm_does_not_expect_a_response(self):
        llm = FakeLLM(fail=True)
        voice = FakeVoice()
        services = make_services(llm, voice)
        module = ListeningComprehension()

        result = module.start(services)

        assert result.expects_response is False
        assert "no listening passage is available" in result.text_response.lower()

    def test_missing_activity_prompt_degrades_gracefully(self):
        class FailingPrompter:
            def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
                raise FileNotFoundError("prompt file missing")

        llm = FakeLLM(responses=["should not be reached"])
        voice = FakeVoice()
        services = make_services(llm, voice)
        services.prompter = FailingPrompter()
        module = ListeningComprehension()

        result = module.start(services)

        assert result.expects_response is False
        assert llm.calls == []

    def test_falls_back_to_a_generic_question_when_model_ignores_the_format(self):
        llm = FakeLLM(responses=["Just a passage with no marker at all."])
        voice = FakeVoice()
        services = make_services(llm, voice)
        module = ListeningComprehension()

        result = module.start(services)

        assert module._passage == "Just a passage with no marker at all."
        assert "What was the passage about?" in result.text_response


class TestListeningComprehensionReplay:
    def test_replay_request_repeats_audio_without_completing(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION])
        voice = FakeVoice(path="/tmp/passage.mp3")
        services = make_services(llm, voice)
        module = ListeningComprehension()
        module.start(services)

        result = module.handle_response("replay please", services)

        assert result.is_complete is False
        assert result.voice_response == "/tmp/passage.mp3"
        assert len(voice.speech_calls) == 2  # initial + replay
        assert module._replay_count == 1


class TestListeningComprehensionGrading:
    def test_correct_answer_is_graded_and_reveals_the_passage(self):
        llm = FakeLLM(responses=[
            PASSAGE_AND_QUESTION,
            "CORRECT\nGenau richtig!",
        ])
        voice = FakeVoice()
        services = make_services(llm, voice)
        module = ListeningComprehension()
        module.start(services)

        result = module.handle_response("It's about everyday life.", services)

        assert result.is_complete is True
        assert "CORRECT" in result.text_response
        assert "Das ist ein kurzer Text" in result.text_response  # passage revealed after grading

    def test_grading_failure_still_completes_gracefully(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION], fail_after=1)
        voice = FakeVoice()
        services = make_services(llm, voice)
        module = ListeningComprehension()
        module.start(services)

        result = module.handle_response("some answer", services)

        assert result.is_complete is True
        assert "Could not grade" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION, "CORRECT\nGut!"])
        voice = FakeVoice()
        services = make_services(llm, voice)
        module = ListeningComprehension()
        module.start(services)
        module.handle_response("an answer", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestListeningComprehensionResults:
    def test_complete_reports_expected_shape(self):
        llm = FakeLLM(responses=[PASSAGE_AND_QUESTION, "CORRECT\nGut!"])
        voice = FakeVoice(path="/tmp/passage.mp3")
        services = make_services(llm, voice)
        module = ListeningComprehension()
        module.start(services)
        module.handle_response("replay", services)
        module.handle_response("an answer", services)

        results = module.complete(services)

        assert results["audio_paths"] == ["/tmp/passage.mp3", "/tmp/passage.mp3"]
        assert results["questions_answered"] == 1
        assert results["replay_count"] == 1
