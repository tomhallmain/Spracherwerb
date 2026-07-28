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
