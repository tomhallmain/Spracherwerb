"""Turns must not run on the GUI thread.

A module that needs an image calls SDRunnerClient.generate_image(), which
polls for the generated file up to a 120-second timeout. Run inline, that
freezes the window for the duration, so these pin the hand-off: the call
returns while the controller is still working, and the result arrives later
through a queued signal.

The controller stand-in blocks on an Event rather than sleeping, so the tests
assert on ordering rather than on elapsed time.
"""

import threading
import time

import pytest

from Spracherwerb.media_generation import MediaEvent, MediaPriority, MediaState
from ui.interaction_panel import InteractionPanel


def pump(qapp, predicate, timeout=5.0):
    """Spin the event loop until *predicate* holds, or give up.

    A signal emitted from a worker thread is queued onto the GUI thread and
    only delivered when the loop runs, which in a test means here.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return False


class FakeController:
    """Session controller whose turns block until released."""

    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {"text_response": "ok"}
        self.error = error
        self.release = threading.Event()
        self.entered = threading.Event()
        self.calls = []

    def has_active_activity(self):
        return True

    def _work(self, label):
        # Snapshot before blocking: a test that changes `result` to tell a
        # superseded turn from its replacement would otherwise have the old
        # call return the new value.
        result = self.result
        self.calls.append(label)
        self.entered.set()
        self.release.wait(timeout=5.0)
        if self.error is not None:
            raise self.error
        return result

    def send_message(self, message):
        return self._work(("send", message))

    def start_activity(self, activity_type):
        return self._work(("start", activity_type))


@pytest.fixture
def panel(qapp):
    controller = FakeController()
    widget = InteractionPanel(session_controller=controller)
    yield widget, controller
    controller.release.set()
    widget.deleteLater()


class TestTurnRunsOffTheGuiThread:
    def test_send_message_returns_while_the_turn_is_still_running(self, panel):
        widget, controller = panel
        widget.input_field.setText("Hund")

        widget.send_message()

        # The call has returned; the controller has not.
        assert controller.entered.wait(timeout=5.0)
        assert controller.release.is_set() is False

    def test_the_turn_runs_on_another_thread(self, panel):
        widget, controller = panel
        main_thread = threading.current_thread().ident
        seen = []
        controller.send_message = lambda m: (
            seen.append(threading.current_thread().ident),
            controller.entered.set(),
            controller.result,
        )[-1]
        widget.input_field.setText("Hund")

        widget.send_message()

        assert controller.entered.wait(timeout=5.0)
        assert seen and seen[0] != main_thread

    def test_input_is_disabled_while_busy_and_restored_after(self, panel, qapp):
        widget, controller = panel
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        assert widget.input_field.isEnabled() is False
        assert widget.send_button.isEnabled() is False

        controller.release.set()
        assert pump(qapp, lambda: widget.input_field.isEnabled())
        assert widget.send_button.isEnabled() is True


class TestResultDelivery:
    def test_result_reaches_the_log_after_the_turn_finishes(self, panel, qapp):
        widget, controller = panel
        controller.result = {"text_response": "Sehr gut"}
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()

        assert pump(qapp, lambda: "Sehr gut" in widget.log_area.toPlainText())

    def test_the_log_records_that_media_appeared(self, panel, qapp):
        """The frame shows it; the log only records that it happened."""
        widget, controller = panel
        controller.result = {"text_response": "x", "media_path": "/tmp/katze.png"}
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()

        assert pump(qapp, lambda: "katze.png" in widget.log_area.toPlainText())

    def test_no_pixel_data_reaches_the_log(self, panel, qapp):
        """Inlining the image would hold a second copy of every one for the
        life of the session, in a log that only grows."""
        widget, controller = panel
        controller.result = {"text_response": "x", "media_path": "/tmp/katze.png"}
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()
        assert pump(qapp, lambda: "katze.png" in widget.log_area.toPlainText())

        assert "base64" not in widget.log_area.toHtml()
        assert "<img" not in widget.log_area.toHtml()

    def test_a_text_only_turn_logs_no_media_notice(self, panel, qapp):
        widget, controller = panel
        controller.result = {"text_response": "just words"}
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()

        assert pump(qapp, lambda: "just words" in widget.log_area.toPlainText())
        assert "shared" not in widget.log_area.toPlainText()

    def test_media_path_is_emitted_after_the_turn_finishes(self, panel, qapp):
        widget, controller = panel
        controller.result = {"text_response": "x", "media_path": "/tmp/a.png"}
        received = []
        widget.media_ready.connect(received.append)

        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()

        assert pump(qapp, lambda: received == ["/tmp/a.png"])

    def test_a_failing_turn_reports_rather_than_raising(self, panel, qapp):
        widget, controller = panel
        controller.error = RuntimeError("boom")
        widget.input_field.setText("Hund")

        widget.send_message()
        assert controller.entered.wait(timeout=5.0)
        controller.release.set()

        assert pump(qapp, lambda: "boom" in widget.log_area.toPlainText())
        assert widget.input_field.isEnabled() is True

    def test_no_activity_answers_without_starting_a_turn(self, qapp):
        controller = FakeController()
        controller.has_active_activity = lambda: False
        widget = InteractionPanel(session_controller=controller)
        widget.input_field.setText("Hund")

        widget.send_message()

        assert controller.calls == []
        assert widget.input_field.isEnabled() is True


class TestSupersededTurns:
    def test_a_second_turn_waits_for_the_first(self, panel, qapp):
        """Two threads inside one module would race on its per-activity state."""
        widget, controller = panel
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.start_activity("grammar_practice")
        # Still only the first call; the second is queued, not running.
        assert controller.calls == [("send", "Hund")]

        controller.entered.clear()
        controller.release.set()
        assert pump(qapp, lambda: len(controller.calls) == 2)
        assert controller.calls[1] == ("start", "grammar_practice")

    def test_the_superseded_turn_result_is_dropped(self, panel, qapp):
        widget, controller = panel
        controller.result = {"text_response": "stale answer"}
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.start_activity("grammar_practice")
        controller.result = {"text_response": "fresh opening"}
        controller.release.set()

        assert pump(qapp, lambda: "fresh opening" in widget.log_area.toPlainText())
        assert "stale answer" not in widget.log_area.toPlainText()

    def test_only_the_latest_queued_turn_runs(self, panel, qapp):
        """The queue holds one turn: rapid mode switching should land on the
        last choice, not replay every intermediate one."""
        widget, controller = panel
        widget.start_activity("vocabulary_builder")
        assert controller.entered.wait(timeout=5.0)

        widget.start_activity("grammar_practice")
        widget.start_activity("writing_practice")

        controller.entered.clear()
        controller.release.set()
        assert pump(qapp, lambda: len(controller.calls) == 2)
        assert controller.calls[1] == ("start", "writing_practice")


class TestMediaProgress:
    """A picture the current turn is waiting on gets a progress message; one
    drawn ahead of time must not touch the frame."""

    def _event(self, state, priority=MediaPriority.NOW, slug="katze"):
        return MediaEvent(1, slug, state, priority=priority)

    def test_the_current_item_reports_progress(self, panel, qapp):
        widget, controller = panel
        pending = []
        widget.media_pending.connect(pending.append)
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.handle_media_event(self._event(MediaState.RUNNING))

        assert pump(qapp, lambda: len(pending) == 1)
        controller.release.set()

    def test_pre_generation_does_not_touch_the_frame(self, panel, qapp):
        """Drawing the next word must not paint over the current picture."""
        widget, controller = panel
        pending = []
        widget.media_pending.connect(pending.append)
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.handle_media_event(
            self._event(MediaState.RUNNING, priority=MediaPriority.AHEAD))

        qapp.processEvents()
        assert pending == []
        controller.release.set()

    def test_a_failed_picture_clears_the_placeholder(self, panel, qapp):
        """Otherwise the frame keeps saying "generating" for good."""
        widget, controller = panel
        unavailable = []
        widget.media_unavailable.connect(lambda: unavailable.append(True))
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.handle_media_event(self._event(MediaState.FAILED))

        assert pump(qapp, lambda: unavailable == [True])
        controller.release.set()

    def test_a_cancelled_picture_clears_the_placeholder(self, panel, qapp):
        widget, controller = panel
        unavailable = []
        widget.media_unavailable.connect(lambda: unavailable.append(True))
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.handle_media_event(self._event(MediaState.CANCELLED))

        assert pump(qapp, lambda: unavailable == [True])
        controller.release.set()

    def test_events_outside_a_turn_are_ignored(self, panel, qapp):
        """An event landing after the turn finished describes a state the
        frame has already moved past."""
        widget, _controller = panel
        pending = []
        unavailable = []
        widget.media_pending.connect(pending.append)
        widget.media_unavailable.connect(lambda: unavailable.append(True))

        widget.handle_media_event(self._event(MediaState.RUNNING))
        widget.handle_media_event(self._event(MediaState.FAILED))

        qapp.processEvents()
        assert pending == []
        assert unavailable == []

    def test_a_ready_event_is_left_to_the_turn_result(self, panel, qapp):
        """The turn carries the path back with its text; acting on READY here
        as well would decode the same file twice."""
        widget, controller = panel
        pending = []
        unavailable = []
        widget.media_pending.connect(pending.append)
        widget.media_unavailable.connect(lambda: unavailable.append(True))
        widget.input_field.setText("Hund")
        widget.send_message()
        assert controller.entered.wait(timeout=5.0)

        widget.handle_media_event(self._event(MediaState.READY))

        qapp.processEvents()
        assert pending == []
        assert unavailable == []
        controller.release.set()
