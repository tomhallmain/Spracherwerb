"""Tests for PronunciationGuide: TTS audio + LLM articulation tips, ungraded."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.pronunciation_guide import ITEMS_PER_SESSION, PronunciationGuide
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


class FakeVoice:
    def __init__(self, path="/tmp/word.mp3", fail=False):
        self._path = path
        self._fail = fail
        self.speech_calls = []

    def generate_speech(self, text, topic="learning"):
        self.speech_calls.append(text)
        if self._fail:
            raise Exception("TTS failed")
        return self._path


class FakeVocabularyPool:
    def __init__(self, entries):
        self._entries = entries

    def get_review_candidates(self, source_language, target_language, limit=20,
                               exclude=None, shuffle=True):
        return list(self._entries[:limit])


def make_services(llm, voice, vocabulary_pool, proficiency_level="intermediate",
                   target_language="de", source_language="en"):
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
        vocabulary_pool=vocabulary_pool,
    )


ENTRIES = [
    {"source_text": "dog", "translated_text": "Hund", "target_article": "der"},
    {"source_text": "cat", "translated_text": "Katze", "target_article": "die"},
]


class TestPronunciationGuideRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(PronunciationGuide)
        assert ActivityRegistry.is_implemented(ActivityType.PRONUNCIATION_GUIDE)
        module = ActivityRegistry.create(ActivityType.PRONUNCIATION_GUIDE)
        assert isinstance(module, PronunciationGuide)


class TestPronunciationGuideStart:
    def test_start_with_no_candidates_does_not_expect_a_response(self):
        services = make_services(FakeLLM(), FakeVoice(), FakeVocabularyPool([]))
        module = PronunciationGuide()

        result = module.start(services)

        assert result.expects_response is False
        assert "no saved vocabulary" in result.text_response.lower()

    def test_plays_tts_and_shows_articulation_tips_for_the_first_item(self):
        llm = FakeLLM(responses=["Round the lips slightly for the initial consonant cluster."])
        voice = FakeVoice(path="/tmp/hund.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()

        result = module.start(services)

        assert result.voice_response == "/tmp/hund.mp3"
        assert "der Hund" in result.text_response
        assert "Round the lips" in result.text_response
        assert voice.speech_calls == ["der Hund"]

    def test_missing_activity_prompt_does_not_block_the_activity(self):
        class FailingPrompter:
            def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
                raise FileNotFoundError("prompt file missing")

        llm = FakeLLM(responses=["Tips."])
        voice = FakeVoice()
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        services.prompter = FailingPrompter()
        module = PronunciationGuide()

        result = module.start(services)

        assert result.expects_response is True
        assert llm.calls[0]['system_prompt'] == ""

    def test_tts_failure_still_shows_tips(self):
        llm = FakeLLM(responses=["Tips."])
        voice = FakeVoice(fail=True)
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()

        result = module.start(services)

        assert result.voice_response is None
        assert "Tips." in result.text_response

    def test_tips_failure_still_plays_audio(self):
        llm = FakeLLM(fail=True)
        voice = FakeVoice(path="/tmp/hund.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()

        result = module.start(services)

        assert result.voice_response == "/tmp/hund.mp3"
        assert "Could not fetch articulation tips" in result.text_response


class TestPronunciationGuideTurns:
    def test_replay_repeats_audio_without_advancing_or_a_new_tips_call(self):
        llm = FakeLLM(responses=["Tips for Hund."])
        voice = FakeVoice(path="/tmp/hund.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()
        module.start(services)

        result = module.handle_response("replay please", services)

        assert result.is_complete is False
        assert result.voice_response == "/tmp/hund.mp3"
        assert len(voice.speech_calls) == 2  # initial + replay
        assert len(llm.calls) == 1  # no second tips call for a replay
        assert module._replay_count == 1

    def test_any_other_response_advances_to_the_next_item(self):
        llm = FakeLLM(responses=["Tips for Hund.", "Tips for Katze."])
        voice = FakeVoice(path="/tmp/word.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()
        module.start(services)

        result = module.handle_response("ok", services)

        assert result.is_complete is False
        assert "die Katze" in result.text_response
        assert "Tips for Katze." in result.text_response

    def test_runs_through_all_items_and_completes(self):
        llm = FakeLLM(responses=["Tips for Hund.", "Tips for Katze."])
        voice = FakeVoice(path="/tmp/word.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()
        module.start(services)

        first = module.handle_response("ok", services)
        second = module.handle_response("ok", services)

        assert first.is_complete is False
        assert second.is_complete is True
        assert "2 item(s) practiced" in second.text_response

    def test_handle_response_after_finished_is_safe(self):
        llm = FakeLLM(responses=["Tips for Hund."])
        voice = FakeVoice()
        services = make_services(llm, voice, FakeVocabularyPool([ENTRIES[0]]))
        module = PronunciationGuide()
        module.start(services)
        module.handle_response("ok", services)

        result = module.handle_response("anything else", services)

        assert result.is_complete is True
        assert "already finished" in result.text_response.lower()


class TestPronunciationGuideResults:
    def test_complete_reports_items_practiced_and_notes(self):
        llm = FakeLLM(responses=["Tips for Hund.", "Tips for Katze."])
        voice = FakeVoice(path="/tmp/word.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(ENTRIES))
        module = PronunciationGuide()
        module.start(services)
        module.handle_response("ok", services)
        module.handle_response("ok", services)

        results = module.complete(services)

        assert results["items_practiced"] == ["Hund", "Katze"]
        assert results["notes"] == ["Tips for Hund.", "Tips for Katze."]

    def test_session_respects_items_per_session_cap(self):
        many_entries = [
            {"source_text": f"word{i}", "translated_text": f"Wort{i}"}
            for i in range(ITEMS_PER_SESSION + 5)
        ]
        llm = FakeLLM(responses=[f"Tips {i}" for i in range(ITEMS_PER_SESSION)])
        voice = FakeVoice(path="/tmp/word.mp3")
        services = make_services(llm, voice, FakeVocabularyPool(many_entries))
        module = PronunciationGuide()
        module.start(services)

        for _ in range(ITEMS_PER_SESSION - 1):
            module.handle_response("ok", services)
        final = module.handle_response("ok", services)

        assert final.is_complete is True
        results = module.complete(services)
        assert len(results["items_practiced"]) == ITEMS_PER_SESSION
