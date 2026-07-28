"""Tests for LearningSession, in particular its optional-callbacks handling.

``_setup_callbacks`` used to leave ``self.callbacks`` unset entirely when no
callbacks dict was passed in (the documented default), so the first call to
any of start/start_activity/process_user_response/complete_current_activity
raised AttributeError on ``self.callbacks``. This went unnoticed because
nothing previously called into LearningSession -- the UI wiring stopped at
LearningEngine (see test_learning_framework.py) and never went through the
session layer above it.
"""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.learning_session import LearningSession
from Spracherwerb.session_config import SessionConfig
from Spracherwerb.stub_learning_module import StubLearningModule


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture
def session_config():
    return SessionConfig({
        "source_language": "en",
        "target_language": "de",
        "proficiency_level": "beginner",
        "enable_pronunciation_practice": False,
    })


class TestLearningSessionWithoutCallbacks:
    def test_full_turn_cycle_with_no_callbacks_dict(self, session_config):
        ActivityRegistry.register(StubLearningModule)
        session = LearningSession(session_config)

        session.start()
        start = session.start_activity("vocabulary_builder")
        assert "Stub activity started" in start["text_response"]

        turn = session.process_user_response("Hund")
        assert turn["text_response"] == "Echo: Hund"

        results = session.complete_current_activity()
        assert results["stub"] is True

    def test_error_path_with_no_callbacks_dict_does_not_mask_the_real_error(self, session_config):
        session = LearningSession(session_config)
        # Started with no learning_engine set up -- process_user_response
        # should raise its own "Session not started" error, not an
        # unrelated AttributeError from missing self.callbacks.
        with pytest.raises(Exception, match="Session not started"):
            session.process_user_response("hallo")


class TestLearningSessionWithPartialCallbacks:
    def test_only_provided_callback_keys_are_invoked(self, session_config):
        ActivityRegistry.register(StubLearningModule)
        error_calls = []
        # Only error_occurred is provided; activity_started/user_response_processed
        # are absent from the dict, not merely None-valued -- this used to make
        # 'key' in self.callbacks true with a None value, crashing on call.
        session = LearningSession(session_config, callbacks={"error_occurred": error_calls.append})

        session.start()
        session.start_activity("vocabulary_builder")
        session.process_user_response("Hund")

        assert error_calls == []

    def test_error_callback_is_invoked_on_failure(self, session_config):
        error_calls = []
        session = LearningSession(session_config, callbacks={"error_occurred": error_calls.append})

        with pytest.raises(Exception):
            session.process_user_response("hallo")

        assert len(error_calls) == 1
        assert "Session not started" in error_calls[0]
