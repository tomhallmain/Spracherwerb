"""Tests for the pure/local-only parts of SDRunnerClient.

These exercise construction, file polling, and graceful failure without a
live sd-runner server -- there's no public endpoint to test against (unlike
Gutenberg/LibriVox/Wiktionary), so anything that requires a real socket
connection is out of scope here and left to manual verification against a
running server.
"""

import pytest

from extensions.sd_runner_client import SDRunnerClient
from utils.config import config
from utils.globals import ImageGenerationType


class TestConstruction:
    def test_resolves_host_and_port_from_config_by_default(self):
        client = SDRunnerClient()
        assert client._host == config.server_host
        assert client._port == config.server_port

    def test_explicit_host_and_port_override_config(self):
        client = SDRunnerClient(host="example.internal", port=1234)
        assert client._host == "example.internal"
        assert client._port == 1234


class TestValidateImageForType:
    def test_redo_prompt_raises_not_implemented(self):
        client = SDRunnerClient()
        with pytest.raises(NotImplementedError):
            client.validate_image_for_type(ImageGenerationType.REDO_PROMPT, "some/image.png")

    def test_other_types_are_a_no_op(self):
        client = SDRunnerClient()
        # Should not raise for any non-REDO_PROMPT type.
        client.validate_image_for_type(ImageGenerationType.REVERT_TO_SIMPLE_GEN, None)
        client.validate_image_for_type(ImageGenerationType.LAST_SETTINGS, None)


class TestWaitForFile:
    def test_returns_the_path_when_the_file_already_exists(self, tmp_path):
        client = SDRunnerClient()
        target = tmp_path / "myword.png"
        target.write_bytes(b"fake-image-bytes")

        result = client._wait_for_file(str(tmp_path), "myword", timeout=5, poll_interval=0.1)

        assert result == str(target)

    def test_matches_any_recognized_image_extension(self, tmp_path):
        client = SDRunnerClient()
        target = tmp_path / "myword.jpeg"
        target.write_bytes(b"fake-image-bytes")

        result = client._wait_for_file(str(tmp_path), "myword", timeout=5, poll_interval=0.1)

        assert result == str(target)

    def test_returns_none_when_the_file_never_appears(self, tmp_path):
        client = SDRunnerClient()

        result = client._wait_for_file(str(tmp_path), "never_appears", timeout=0.3, poll_interval=0.1)

        assert result is None

    def test_does_not_match_a_different_filename(self, tmp_path):
        client = SDRunnerClient()
        (tmp_path / "other_word.png").write_bytes(b"fake-image-bytes")

        result = client._wait_for_file(str(tmp_path), "myword", timeout=0.3, poll_interval=0.1)

        assert result is None


class TestGenerateImage:
    def test_returns_none_when_the_run_request_fails(self, monkeypatch, tmp_path):
        client = SDRunnerClient()

        def boom(*args, **kwargs):
            raise Exception("connection refused")

        monkeypatch.setattr(client, "run", boom)

        result = client.generate_image("a prompt", str(tmp_path), "myword")

        assert result is None

    def test_polls_for_the_file_after_a_successful_run_request(self, monkeypatch, tmp_path):
        client = SDRunnerClient()
        monkeypatch.setattr(client, "run", lambda *args, **kwargs: None)
        (tmp_path / "myword.png").write_bytes(b"fake-image-bytes")

        result = client.generate_image(
            "a prompt", str(tmp_path), "myword", timeout=5, poll_interval=0.1)

        assert result == str(tmp_path / "myword.png")
