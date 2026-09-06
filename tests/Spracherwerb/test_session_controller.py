"""Tests for SessionController, the UI-facing session/activity orchestrator."""

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.session_controller import SessionController
from Spracherwerb.stub_learning_module import StubLearningModule


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


class TestSessionController:
    def test_send_message_before_start_activity_raises(self):
        controller = SessionController()
        with pytest.raises(Exception, match="start_activity"):
            controller.send_message("hallo")

    def test_start_activity_creates_a_session_lazily(self):
        ActivityRegistry.register(StubLearningModule)
        controller = SessionController()
        assert controller.has_active_activity() is False

        result = controller.start_activity("vocabulary_builder")

        assert controller.has_active_activity() is True
        assert "Stub activity started" in result["text_response"]

    def test_send_message_after_start_activity_reaches_the_module(self):
        ActivityRegistry.register(StubLearningModule)
        controller = SessionController()
        controller.start_activity("vocabulary_builder")

        result = controller.send_message("Hund")

        assert result["text_response"] == "Echo: Hund"

    def test_placeholder_activity_still_responds_without_error(self):
        # No module registered for writing_practice -- ActivityRegistry
        # falls back to the placeholder, which should still round-trip
        # cleanly through the controller rather than raising.
        controller = SessionController()

        result = controller.start_activity("writing_practice")

        assert "not implemented yet" in result["text_response"].lower()

    def test_switching_activity_completes_the_previous_one(self):
        ActivityRegistry.register(StubLearningModule)
        controller = SessionController()
        controller.start_activity("vocabulary_builder")
        controller.send_message("Hund")

        controller.start_activity("grammar_practice")

        session = controller.session_manager.get_active_session()
        completed = session.state.activities_completed
        assert len(completed) == 1
        assert completed[0]["activity"] == "vocabulary_builder"
        assert completed[0]["results"]["module_results"]["turns"] == 1

    def test_reset_drops_the_session(self):
        ActivityRegistry.register(StubLearningModule)
        controller = SessionController()
        controller.start_activity("vocabulary_builder")

        controller.reset()

        assert controller.has_active_activity() is False
        assert controller.session_manager.get_active_session() is None

    def test_reset_before_any_activity_is_a_no_op(self):
        controller = SessionController()
        controller.reset()
        assert controller.has_active_activity() is False


class FakeSession:
    """Stands in for LearningSession, recording what gets attached to it."""

    def __init__(self):
        self.media_listeners = []

    def add_media_listener(self, listener):
        self.media_listeners.append(listener)
        return True

    def start_activity(self, activity_type):
        return {"text_response": f"started {activity_type}"}

    def process_user_response(self, message):
        return {"text_response": f"echo {message}"}

    def complete_current_activity(self):
        return {}


class FakeSessionManager:
    """Hands out a fresh FakeSession per session, as SessionManager does."""

    def __init__(self):
        self.session = None

    def create_session(self, config, callbacks):
        self.session = FakeSession()
        return "session-id"

    def start_session(self, session_id):
        return True

    def get_active_session(self):
        return self.session

    def end_session(self):
        self.session = None


class TestMediaListener:
    """Generation progress has to reach the UI, including across the session
    that a language change throws away."""

    def test_a_listener_set_first_reaches_the_session(self):
        manager = FakeSessionManager()
        controller = SessionController(session_manager=manager)
        listener = lambda event: None

        controller.set_media_listener(listener)
        controller.start_activity("vocabulary_builder")

        assert manager.session.media_listeners == [listener]

    def test_a_listener_set_later_reaches_the_live_session(self):
        manager = FakeSessionManager()
        controller = SessionController(session_manager=manager)
        controller.start_activity("vocabulary_builder")
        listener = lambda event: None

        controller.set_media_listener(listener)

        assert manager.session.media_listeners == [listener]

    def test_the_session_after_a_reset_gets_it_too(self):
        """reset() drops the session on a language change; the next one still
        needs to report progress."""
        manager = FakeSessionManager()
        controller = SessionController(session_manager=manager)
        listener = lambda event: None
        controller.set_media_listener(listener)
        controller.start_activity("vocabulary_builder")

        controller.reset()
        controller.start_activity("grammar_practice")

        assert manager.session.media_listeners == [listener]

    def test_no_listener_is_harmless(self):
        manager = FakeSessionManager()
        controller = SessionController(session_manager=manager)

        controller.start_activity("vocabulary_builder")

        assert manager.session.media_listeners == []

    def test_setting_one_before_any_session_does_not_create_one(self):
        manager = FakeSessionManager()
        controller = SessionController(session_manager=manager)

        controller.set_media_listener(lambda event: None)

        assert manager.session is None
