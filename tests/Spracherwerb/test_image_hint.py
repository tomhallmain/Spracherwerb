"""Tests for the shared SD Runner image-generation/reuse helper."""

from Spracherwerb import image_hint


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
    def __init__(self, sd_client):
        self.sd_client = sd_client


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


class TestRequestGeneration:
    def test_returns_none_when_no_client(self, tmp_path):
        result = image_hint.request_generation(FakeServices(None), tmp_path, "word", "a prompt")
        assert result is None

    def test_calls_generate_image_with_the_prompt(self, tmp_path):
        client = FakeSDClient(image_path=str(tmp_path / "word.png"))
        services = FakeServices(client)

        result = image_hint.request_generation(services, tmp_path, "word", "a prompt")

        assert result == str(tmp_path / "word.png")
        assert client.generate_calls == [("a prompt", str(tmp_path), "word")]

    def test_returns_none_when_generation_raises(self, tmp_path):
        client = FakeSDClient(raise_on_generate=True)
        services = FakeServices(client)

        assert image_hint.request_generation(services, tmp_path, "word", "a prompt") is None

    def test_creates_the_cache_dir_if_missing(self, tmp_path):
        cache_dir = tmp_path / "nested" / "dir"
        client = FakeSDClient(image_path=str(cache_dir / "word.png"))
        services = FakeServices(client)

        image_hint.request_generation(services, cache_dir, "word", "a prompt")

        assert cache_dir.exists()
