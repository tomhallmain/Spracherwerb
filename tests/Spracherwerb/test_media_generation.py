"""Background media generation.

The point of the service is that a request returns while the picture is still
being drawn, so these assert on ordering and on the events a listener sees,
never on elapsed time. The client stand-in blocks on an Event, which makes the
"still running" window deterministic.
"""

import threading
import time
from pathlib import Path

import pytest

from Spracherwerb.media_generation import (
    MediaEvent,
    MediaGenerationService,
    MediaPriority,
    MediaState,
    find_cached,
)


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class FakeSDClient:
    """Stands in for SDRunnerClient, blocking until released."""

    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.gate = threading.Event()
        self.gate.set()
        self.produce_file = True
        self._lock = threading.Lock()

    def generate_image(self, positive_prompt, target_dir, filename, **kwargs):
        with self._lock:
            self.calls.append(filename)
        self.entered.set()
        self.gate.wait(timeout=5.0)
        if not self.produce_file:
            return None
        path = Path(target_dir) / f"{filename}.png"
        path.write_bytes(b"generated")
        return str(path)

    def call_order(self):
        with self._lock:
            return list(self.calls)


class Recorder:
    """Collects events from the worker thread."""

    def __init__(self):
        self._events = []
        self._lock = threading.Lock()

    def __call__(self, event):
        with self._lock:
            self._events.append(event)

    def events(self):
        with self._lock:
            return list(self._events)

    def states(self, slug):
        return [e.state for e in self.events() if e.slug == slug]

    def ready_path(self, slug):
        for event in self.events():
            if event.slug == slug and event.state is MediaState.READY:
                return event.path
        return None


@pytest.fixture
def service(tmp_path):
    client = FakeSDClient()
    svc = MediaGenerationService(sd_client=client, cache_dir=tmp_path)
    recorder = Recorder()
    svc.add_listener(recorder)
    yield svc, client, recorder
    # Release first: shutdown() joins the worker, and a test that left the
    # client blocked would otherwise stall teardown until the join times out.
    client.gate.set()
    svc.shutdown()


class TestFindCached:
    def test_it_finds_a_generated_file(self, tmp_path):
        (tmp_path / "katze.png").write_bytes(b"x")
        assert find_cached(tmp_path, "katze") == str(tmp_path / "katze.png")

    def test_it_accepts_any_known_extension(self, tmp_path):
        (tmp_path / "katze.webp").write_bytes(b"x")
        assert find_cached(tmp_path, "katze") is not None

    def test_a_miss_is_none(self, tmp_path):
        assert find_cached(tmp_path, "katze") is None

    def test_it_does_not_match_another_slug(self, tmp_path):
        (tmp_path / "hund.png").write_bytes(b"x")
        assert find_cached(tmp_path, "katze") is None


class TestRequestDoesNotBlock:
    def test_the_call_returns_while_generation_runs(self, service):
        """The whole point: the tutor keeps talking while the picture is drawn."""
        svc, client, _ = service
        client.gate.clear()

        job_id = svc.request("katze", "a cat")

        assert job_id is not None
        assert client.entered.wait(timeout=5.0)
        assert client.gate.is_set() is False   # still generating
        client.gate.set()

    def test_without_a_client_there_is_nothing_to_request(self, tmp_path):
        svc = MediaGenerationService(sd_client=None, cache_dir=tmp_path)
        assert svc.request("katze", "a cat") is None

    def test_a_missing_cache_dir_is_a_caller_error(self):
        svc = MediaGenerationService(sd_client=FakeSDClient())
        with pytest.raises(ValueError):
            svc.request("katze", "a cat")


class TestDelivery:
    def test_a_ready_event_carries_the_path(self, service, tmp_path):
        svc, _, recorder = service
        svc.request("katze", "a cat")

        assert wait_for(lambda: recorder.ready_path("katze") is not None)
        assert recorder.ready_path("katze") == str(tmp_path / "katze.png")

    def test_a_cached_file_skips_generation(self, service, tmp_path):
        """A hit is a file-existence check; it must not wait behind the queue
        or redraw something already on disk."""
        svc, client, recorder = service
        (tmp_path / "katze.png").write_bytes(b"already here")

        svc.request("katze", "a cat")

        assert wait_for(lambda: recorder.ready_path("katze") is not None)
        assert client.call_order() == []

    def test_a_generation_that_produces_nothing_reports_failure(self, service):
        svc, client, recorder = service
        client.produce_file = False

        svc.request("katze", "a cat")

        assert wait_for(lambda: MediaState.FAILED in recorder.states("katze"))

    def test_a_raising_client_reports_failure(self, service):
        svc, client, recorder = service

        def boom(**kwargs):
            raise RuntimeError("sd-runner is down")

        client.generate_image = boom
        svc.request("katze", "a cat")

        assert wait_for(lambda: MediaState.FAILED in recorder.states("katze"))
        failure = [e for e in recorder.events() if e.state is MediaState.FAILED][0]
        assert "sd-runner is down" in failure.error

    def test_a_failing_listener_does_not_stop_the_queue(self, service):
        """One bad consumer must not take generation down with it."""
        svc, client, recorder = service
        svc.add_listener(lambda event: (_ for _ in ()).throw(RuntimeError("bad")))

        svc.request("katze", "a cat")

        assert wait_for(lambda: recorder.ready_path("katze") is not None)


class TestDeduplication:
    def test_the_same_slug_is_not_queued_twice(self, service):
        svc, client, _ = service
        client.gate.clear()

        first = svc.request("katze", "a cat")
        second = svc.request("katze", "a cat again")

        assert first == second
        client.gate.set()
        assert wait_for(lambda: client.call_order() == ["katze"])
        time.sleep(0.1)
        assert client.call_order() == ["katze"]

    def test_is_pending_reports_queued_work(self, service):
        svc, client, _ = service
        client.gate.clear()

        svc.request("katze", "a cat")

        assert wait_for(lambda: svc.is_pending("katze"))
        client.gate.set()


class TestPriority:
    def _occupy_worker(self, svc, client):
        """Hold the worker on a primer job so ordering is deterministic."""
        client.gate.clear()
        svc.request("primer", "primer")
        assert client.entered.wait(timeout=5.0)

    def test_a_now_request_runs_before_queued_pre_generation(self, service):
        svc, client, _ = service
        self._occupy_worker(svc, client)

        svc.request("later", "later item", priority=MediaPriority.AHEAD)
        svc.request("current", "current item", priority=MediaPriority.NOW)

        client.gate.set()
        assert wait_for(lambda: len(client.call_order()) == 3)
        assert client.call_order() == ["primer", "current", "later"]

    def test_pre_generation_keeps_its_order(self, service):
        svc, client, _ = service
        self._occupy_worker(svc, client)

        svc.request_ahead([("one", "1"), ("two", "2"), ("three", "3")])

        client.gate.set()
        assert wait_for(lambda: len(client.call_order()) == 4)
        assert client.call_order() == ["primer", "one", "two", "three"]

    def test_reaching_a_pre_generated_item_promotes_it(self, service):
        """The learner arrives at an item already queued behind the rest of the
        plan; it should jump the queue rather than wait its turn."""
        svc, client, _ = service
        self._occupy_worker(svc, client)
        svc.request_ahead([("one", "1"), ("two", "2"), ("three", "3")])

        promoted = svc.request("three", "3", priority=MediaPriority.NOW)

        client.gate.set()
        assert wait_for(lambda: len(client.call_order()) == 4)
        assert client.call_order() == ["primer", "three", "one", "two"]
        assert promoted is not None


class TestCancellation:
    def test_cancelling_a_group_drops_its_queued_work(self, service):
        svc, client, recorder = service
        client.gate.clear()
        svc.request("primer", "primer")
        assert client.entered.wait(timeout=5.0)
        svc.request_ahead([("one", "1"), ("two", "2")], group="vocab")

        svc.cancel_group("vocab")

        assert MediaState.CANCELLED in recorder.states("one")
        assert MediaState.CANCELLED in recorder.states("two")
        client.gate.set()
        assert wait_for(lambda: "primer" in client.call_order())
        time.sleep(0.1)
        assert client.call_order() == ["primer"]

    def test_another_group_is_left_alone(self, service):
        svc, client, recorder = service
        client.gate.clear()
        svc.request("primer", "primer")
        assert client.entered.wait(timeout=5.0)
        svc.request("keep", "keep", group="dialogue")
        svc.request("drop", "drop", group="vocab")

        svc.cancel_group("vocab")
        client.gate.set()

        assert wait_for(lambda: recorder.ready_path("keep") is not None)
        assert MediaState.CANCELLED in recorder.states("drop")

    def test_a_running_job_reports_cancelled_rather_than_ready(self, service):
        """sd-runner has no cancel, so it finishes -- but nobody is waiting for
        it any more, and a listener must not be told it is ready."""
        svc, client, recorder = service
        client.gate.clear()
        svc.request("katze", "a cat", group="vocab")
        assert client.entered.wait(timeout=5.0)

        svc.cancel_group("vocab")
        client.gate.set()

        assert wait_for(lambda: MediaState.CANCELLED in recorder.states("katze"))
        assert MediaState.READY not in recorder.states("katze")

    def test_cancel_all_clears_the_queue(self, service):
        svc, client, _ = service
        client.gate.clear()
        svc.request("primer", "primer")
        assert client.entered.wait(timeout=5.0)
        svc.request_ahead([("one", "1"), ("two", "2")])

        svc.cancel_all()

        assert svc.pending_count() == 0
        client.gate.set()


class TestShutdown:
    def test_shutdown_stops_the_worker(self, tmp_path):
        client = FakeSDClient()
        svc = MediaGenerationService(sd_client=client, cache_dir=tmp_path)
        svc.request("katze", "a cat")
        assert wait_for(lambda: "katze" in client.call_order())

        svc.shutdown()

        assert svc.pending_count() == 0

    def test_shutdown_is_safe_without_any_work(self, tmp_path):
        MediaGenerationService(sd_client=FakeSDClient(), cache_dir=tmp_path).shutdown()


class TestEventShape:
    def test_an_event_carries_its_group(self, service):
        svc, _, recorder = service
        svc.request("katze", "a cat", group="vocab")

        assert wait_for(lambda: recorder.ready_path("katze") is not None)
        assert all(e.group == "vocab" for e in recorder.events())

    def test_events_are_frozen(self):
        event = MediaEvent(1, "katze", MediaState.READY)
        with pytest.raises(Exception):
            event.slug = "hund"
