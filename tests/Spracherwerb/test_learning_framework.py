"""Tests for the learning module framework (Phase 0)."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ActivityStartResult, ActivityTurnResult
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.learning_engine import LearningEngine
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.session_context import SessionContext
from Spracherwerb.stub_learning_module import StubLearningModule
from utils.vocabulary_pool import VocabularyPool


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture
def session_context():
    return SessionContext(
        start_time=0.0,
        activities_completed=[],
        vocabulary_learned=[],
        grammar_points_covered=[],
        time_spent=0.0,
    )


@pytest.fixture
def session_config():
    return SessionConfig(
        {
            "source_language": "en",
            "target_language": "de",
            "proficiency_level": "beginner",
            "enable_pronunciation_practice": False,
        }
    )


def test_activity_type_from_value():
    assert ActivityType.from_value("grammar_practice") == ActivityType.GRAMMAR_PRACTICE
    with pytest.raises(ValueError):
        ActivityType.from_value("not_a_module")


def test_registry_registers_all_placeholders():
    ActivityRegistry.register_defaults()
    assert len(ActivityRegistry.registered_types()) == len(ActivityType)
    assert not ActivityRegistry.is_implemented(ActivityType.VOCABULARY_BUILDER)


def test_registry_allows_module_override():
    ActivityRegistry.register(StubLearningModule)
    assert ActivityRegistry.is_implemented(ActivityType.VOCABULARY_BUILDER)
    module = ActivityRegistry.create(ActivityType.VOCABULARY_BUILDER)
    assert isinstance(module, StubLearningModule)


def test_learning_engine_runs_stub_module(session_config, session_context):
    ActivityRegistry.register(StubLearningModule)
    engine = LearningEngine(
        session_config,
        session_context,
        vocabulary_pool=VocabularyPool(),
    )

    start = engine.start_activity("vocabulary_builder")
    assert "Stub activity started" in start["text_response"]
    assert session_context.current_activity == "vocabulary_builder"

    turn_one = engine.process_user_response("Hund")
    assert turn_one["text_response"] == "Echo: Hund"
    assert turn_one["is_complete"] is False

    turn_two = engine.process_user_response("Katze")
    assert turn_two["is_complete"] is True

    results = engine.complete_activity()
    assert results["stub"] is True
    assert results["turns"] == 2
    assert len(session_context.activities_completed) == 1


class FakeVoice:
    def __init__(self):
        self.spoken = []

    def generate_speech(self, text, topic="learning"):
        self.spoken.append(text)
        return f"speech_{len(self.spoken)}.mp3"


class VoiceTextModule(StubLearningModule):
    def start(self, services):
        return ActivityStartResult(
            text_response="Label: Beispielsatz.",
            activity_type=self.activity_type.value,
            voice_text="Beispielsatz.",
        )

    def handle_response(self, user_text, services):
        return ActivityTurnResult(
            text_response="Nothing worth reading aloud.",
            activity_type=self.activity_type.value,
            voice_text="",
        )


def test_learning_engine_speaks_voice_text_in_place_of_text_response(session_context):
    ActivityRegistry.register(VoiceTextModule)
    session_config = SessionConfig({
        "source_language": "en",
        "target_language": "de",
        "enable_pronunciation_practice": True,
    })
    engine = LearningEngine(session_config, session_context, vocabulary_pool=VocabularyPool())
    engine.voice = FakeVoice()

    start = engine.start_activity("vocabulary_builder")
    turn = engine.process_user_response("anything")

    assert engine.voice.spoken == ["Beispielsatz."]
    assert start["voice_response"] == "speech_1.mp3"
    assert turn["voice_response"] is None


def test_unimplemented_module_start(session_config, session_context):
    engine = LearningEngine(session_config, session_context)
    start = engine.start_activity("writing_practice")
    assert "not implemented yet" in start["text_response"].lower()
    assert start["expects_response"] is False


def test_session_config_includes_language_fields(session_config):
    payload = session_config.to_dict()
    assert payload["source_language"] == "en"
    assert payload["target_language"] == "de"
    assert payload["proficiency_level"] == "beginner"
    assert session_config.validate() is True
