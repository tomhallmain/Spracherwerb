"""Tests for the shared SD Runner image-generation/reuse helper.

Generation runs on MediaGenerationService's worker, so these use a real
service with a stub client rather than mocking the helper's internals -- the
thing worth pinning is that only the current item waits.
"""

import pytest

from Spracherwerb import image_hint
from Spracherwerb.media_generation import MediaGenerationService


class FakeSDClient:
    def __init__(self, reachable=True, image_path=None, raise_on_generate=False):
        self._reachable = reachable
        self._image_path = image_path
        self._raise_on_generate = raise_on_generate
        self.generate_calls = []

    def is_reachable(self):
        return self._reachable

    def generate_image(self, positive_prompt, target_dir, filename, **kwargs):
        self.generate_calls.append((positive_prompt, target_dir, filename))
        if self._raise_on_generate:
            raise Exception("generation failed")
        return self._image_path


class FakeServices:
    def __init__(self, sd_client, media=None):
        self.sd_client = sd_client
        self.media = media


@pytest.fixture
def services_with_media(tmp_path):
    """Services carrying a real generation service over a stub client."""
    def build(client):
        service = MediaGenerationService(sd_client=client, cache_dir=tmp_path)
        built.append(service)
        return FakeServices(client, media=service)
    built = []
    yield build
    for service in built:
        service.shutdown()


class TestIsSdAvailable:
    def test_true_when_reachable(self):
        assert image_hint.is_sd_available(FakeServices(FakeSDClient(reachable=True))) is True

    def test_false_when_unreachable(self):
        assert image_hint.is_sd_available(FakeServices(FakeSDClient(reachable=False))) is False

    def test_false_when_no_client(self):
        assert image_hint.is_sd_available(FakeServices(sd_client=None)) is False

    def test_false_when_reachability_check_raises(self):
        class RaisingClient:
            def is_reachable(self):
                raise Exception("boom")

        assert image_hint.is_sd_available(FakeServices(RaisingClient())) is False


class TestFindCachedImage:
    def test_returns_none_when_nothing_cached(self, tmp_path):
        assert image_hint.find_cached_image(tmp_path, "word") is None

    def test_finds_a_cached_file_by_extension(self, tmp_path):
        (tmp_path / "word.png").write_bytes(b"data")
        assert image_hint.find_cached_image(tmp_path, "word") == str(tmp_path / "word.png")


class TestGenerateNow:
    def test_returns_none_without_a_generation_service(self, tmp_path):
        assert image_hint.generate_now(
            FakeServices(None), tmp_path, "word", "a prompt") is None

    def test_it_waits_for_the_current_item(self, services_with_media, tmp_path):
        """The one request that blocks: _build_prompt asks a different question
        with a picture than without, so the wording needs the answer."""
        client = FakeSDClient(image_path=str(tmp_path / "word.png"))
        services = services_with_media(client)

        result = image_hint.generate_now(services, tmp_path, "word", "a prompt")

        assert result == str(tmp_path / "word.png")
        assert client.generate_calls == [("a prompt", str(tmp_path), "word")]

    def test_a_cached_file_is_returned_without_generating(self, services_with_media, tmp_path):
        (tmp_path / "word.png").write_bytes(b"already here")
        client = FakeSDClient()
        services = services_with_media(client)

        result = image_hint.generate_now(services, tmp_path, "word", "a prompt")

        assert result == str(tmp_path / "word.png")
        assert client.generate_calls == []

    def test_a_failed_generation_is_a_missing_picture_not_an_error(
        self, services_with_media, tmp_path
    ):
        client = FakeSDClient(raise_on_generate=True)
        services = services_with_media(client)

        assert image_hint.generate_now(
            services, tmp_path, "word", "a prompt", timeout=5) is None

    def test_it_gives_up_rather_than_waiting_forever(self, services_with_media, tmp_path):
        """Past the timeout the activity carries on without a picture; the file
        still lands in the cache for next time."""
        import threading

        client = FakeSDClient(image_path=str(tmp_path / "word.png"))
        release = threading.Event()
        original = client.generate_image

        def slow(**kwargs):
            release.wait(timeout=5.0)
            return original(**kwargs)

        client.generate_image = slow
        services = services_with_media(client)

        result = image_hint.generate_now(
            services, tmp_path, "word", "a prompt", timeout=0.2)

        assert result is None
        release.set()


class TestGenerateAhead:
    def test_it_queues_everything_and_returns(self, services_with_media, tmp_path):
        import time

        client = FakeSDClient(image_path=str(tmp_path / "one.png"))
        services = services_with_media(client)

        image_hint.generate_ahead(
            services, tmp_path, [("one", "1"), ("two", "2")], group="vocab")

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and len(client.generate_calls) < 2:
            time.sleep(0.005)
        assert [call[2] for call in client.generate_calls] == ["one", "two"]

    def test_cached_items_are_not_queued(self, services_with_media, tmp_path):
        (tmp_path / "one.png").write_bytes(b"already here")
        (tmp_path / "two.png").write_bytes(b"already here")
        client = FakeSDClient()
        services = services_with_media(client)

        image_hint.generate_ahead(services, tmp_path, [("one", "1"), ("two", "2")])

        assert services.media.pending_count() == 0

    def test_it_is_a_no_op_without_a_generation_service(self, tmp_path):
        image_hint.generate_ahead(FakeServices(None), tmp_path, [("one", "1")])


class TestCancelPending:
    def test_it_drops_the_group_still_queued(self, services_with_media, tmp_path):
        """Ending an activity should not leave the next one's picture waiting
        behind words nobody is going to be asked about."""
        import threading
        import time

        client = FakeSDClient(image_path=str(tmp_path / "one.png"))
        release = threading.Event()
        original = client.generate_image

        def slow(**kwargs):
            release.wait(timeout=5.0)
            return original(**kwargs)

        client.generate_image = slow
        services = services_with_media(client)
        image_hint.generate_ahead(
            services, tmp_path, [("one", "1"), ("two", "2"), ("three", "3")],
            group="vocab")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not client.generate_calls:
            time.sleep(0.005)

        image_hint.cancel_pending(services, "vocab")

        assert services.media.pending_count() == 0
        release.set()

    def test_another_group_is_untouched(self, services_with_media, tmp_path):
        import time

        client = FakeSDClient(image_path=str(tmp_path / "keep.png"))
        services = services_with_media(client)
        image_hint.generate_ahead(services, tmp_path, [("keep", "k")], group="other")

        image_hint.cancel_pending(services, "vocab")

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not client.generate_calls:
            time.sleep(0.005)
        assert [call[2] for call in client.generate_calls] == ["keep"]

    def test_it_is_a_no_op_without_a_generation_service(self, tmp_path):
        image_hint.cancel_pending(FakeServices(None), "vocab")
