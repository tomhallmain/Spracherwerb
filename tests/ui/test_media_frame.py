"""Behaviour of the media frame.

Rendering and VLC embedding need a real display, so what is pinned here is
everything reachable headlessly: type dispatch, the fit rule, state after each
transition, and that a bad path reports rather than failing silently.
"""

import pytest
from PySide6.QtGui import QImage

from ui.media_frame import MediaFrame, MediaType, scale_dims


@pytest.fixture
def frame(qapp):
    widget = MediaFrame()
    yield widget
    widget.release_media()


def write_image(path, width=40, height=30, fmt="PNG"):
    """Write a real image file; QImageReader has to be able to decode it."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0x336699)
    assert image.save(str(path), fmt)
    return str(path)


class TestScaleDims:
    def test_an_image_that_already_fits_is_untouched(self):
        assert scale_dims((100, 50), (200, 200)) == (100, 50)

    def test_a_wider_image_is_bounded_by_width(self):
        assert scale_dims((400, 100), (200, 200)) == (200, 50)

    def test_a_taller_image_is_bounded_by_height(self):
        assert scale_dims((100, 400), (200, 200)) == (50, 200)

    def test_maximize_grows_a_smaller_image_to_the_box(self):
        assert scale_dims((100, 50), (200, 200), maximize=True) == (200, 100)

    def test_without_maximize_a_smaller_image_stays_small(self):
        assert scale_dims((100, 50), (200, 200), maximize=False) == (100, 50)

    @pytest.mark.parametrize(
        "dims", [(100, 50), (50, 100), (16, 9), (9, 16), (1000, 3), (3, 1000)]
    )
    def test_the_result_always_fits_the_box(self, dims):
        """Growing to meet one side without checking the other overflows: a
        100x50 image in a 200x200 box became 400x200, cropping an animation."""
        width, height = scale_dims(dims, (200, 200), maximize=True)
        assert width <= 200 and height <= 200

    def test_a_square_image_in_a_square_box_is_unchanged(self):
        assert scale_dims((200, 200), (200, 200), maximize=True) == (200, 200)

    def test_zero_dimensions_do_not_divide_by_zero(self):
        assert scale_dims((0, 0), (200, 200), maximize=True) == (200, 200)


class TestTypeDispatch:
    @pytest.mark.parametrize(
        "name", ["clip.mp4", "clip.MKV", "clip.webm", "clip.mov", "clip.m4v"]
    )
    def test_video_extensions_are_recognised(self, name):
        assert MediaFrame._is_video(name) is True

    @pytest.mark.parametrize("name", ["still.png", "still.jpg", "notes.txt"])
    def test_non_video_extensions_are_not(self, name):
        assert MediaFrame._is_video(name) is False

    def test_animation_candidates_are_selected_by_extension(self):
        assert MediaFrame._is_animated_candidate("a.gif") is True
        assert MediaFrame._is_animated_candidate("a.webp") is True
        assert MediaFrame._is_animated_candidate("a.jpg") is False

    def test_a_still_png_is_a_candidate_but_not_animated(self, qapp, tmp_path):
        """Every .png has to be considered, since APNG shares the extension --
        but the check must not call an ordinary still animated."""
        path = write_image(tmp_path / "still.png")
        assert MediaFrame._is_animated_candidate(path) is True
        assert MediaFrame._is_animated(path) is False


class TestShowImage:
    def test_a_still_image_is_displayed(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        assert frame.current_media_type() is MediaType.IMAGE
        assert frame._current_pixmap is not None
        assert frame._placeholder_label.isHidden() is True

    def test_the_full_resolution_pixmap_is_kept(self, frame, tmp_path):
        """Rescaling a scaled copy on every resize compounds the loss, so the
        source has to survive at its original size."""
        frame.show_media(write_image(tmp_path / "word.png", width=640, height=480))

        assert frame._current_pixmap.width() == 640
        assert frame._current_pixmap.height() == 480

    def test_resizing_does_not_shrink_the_source(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png", width=640, height=480))
        frame.resize(200, 150)
        frame.resize(900, 700)

        assert frame._current_pixmap.width() == 640
        assert frame._current_pixmap.height() == 480

    def test_the_path_is_recorded(self, frame, tmp_path):
        path = write_image(tmp_path / "word.png")
        frame.show_media(path)
        assert frame.path == path


class TestMissingAndUnreadable:
    def test_a_missing_path_clears_rather_than_erroring(self, frame, tmp_path):
        frame.show_media(str(tmp_path / "does_not_exist.png"))

        assert frame.current_media_type() is MediaType.NONE
        assert frame.path is None

    def test_an_empty_path_clears(self, frame):
        frame.show_media("")
        assert frame.current_media_type() is MediaType.NONE

    def test_none_clears(self, frame):
        frame.show_media(None)
        assert frame.current_media_type() is MediaType.NONE

    def test_an_undecodable_file_reports_its_name(self, frame, tmp_path):
        """Silence would leave the previous image up, which reads as success."""
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"this is not a png")

        frame.show_media(str(broken))

        assert frame._placeholder_label.isHidden() is False
        assert "broken.png" in frame._placeholder_label.text()
        assert frame.current_media_type() is MediaType.NONE


class TestClearAndRelease:
    def test_clear_drops_the_image(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        frame.clear()

        assert frame.current_media_type() is MediaType.NONE
        assert frame._current_pixmap is None
        assert frame.path is None

    def test_clear_is_safe_with_nothing_displayed(self, frame):
        frame.clear()
        frame.clear()
        assert frame.current_media_type() is MediaType.NONE

    def test_release_media_drops_the_pixmap_and_stops_polling(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        frame.release_media()

        assert frame._current_pixmap is None
        assert frame._mouse_poll_timer.isActive() is False
        assert frame._playback_timer.isActive() is False

    def test_release_media_is_safe_to_repeat(self, frame):
        frame.release_media()
        frame.release_media()


class TestPending:
    def test_pending_shows_a_message_and_no_media(self, frame):
        frame.show_pending()

        assert frame._placeholder_label.isHidden() is False
        assert frame._placeholder_label.text() != ""
        assert frame.current_media_type() is MediaType.NONE
        assert frame.path is None

    def test_a_caption_is_used_when_given(self, frame):
        frame.show_pending("Drawing a cat")
        assert frame._placeholder_label.text() == "Drawing a cat"

    def test_media_replaces_the_pending_message(self, frame, tmp_path):
        frame.show_pending()

        frame.show_media(write_image(tmp_path / "word.png"))

        assert frame._placeholder_label.isHidden() is True
        assert frame.current_media_type() is MediaType.IMAGE

    def test_pending_replaces_a_displayed_image(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        frame.show_pending()

        assert frame.current_media_type() is MediaType.NONE
        assert frame._placeholder_label.isHidden() is False


class TestSurfaceSwitching:
    def test_the_image_surface_is_shown_for_a_still(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        assert frame._graphics_view.isHidden() is False
        assert frame._animated_label.isHidden() is True

    def test_the_image_surface_is_hidden_behind_a_placeholder(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))

        frame.show_pending()

        assert frame._graphics_view.isHidden() is True


class TestFillCanvas:
    def test_it_defaults_to_off(self, frame):
        assert frame.fill_canvas is False

    def test_it_can_be_turned_on_without_reloading(self, frame, tmp_path):
        frame.show_media(write_image(tmp_path / "word.png"))
        pixmap = frame._current_pixmap

        frame.set_fill_canvas(True)

        assert frame.fill_canvas is True
        # Same pixmap object: changing the fit mode is a view transform, not a
        # reason to decode the file again.
        assert frame._current_pixmap is pixmap

    def test_it_is_safe_with_nothing_displayed(self, frame):
        frame.set_fill_canvas(True)
        assert frame.fill_canvas is True


class TestVideoWithoutVlc:
    def test_a_video_reports_when_playback_is_unavailable(
        self, frame, tmp_path, monkeypatch
    ):
        """python-vlc imports fine without the VLC runtime behind it, so this
        is a real deployment state, not a hypothetical."""
        monkeypatch.setattr(frame, "vlc_media_player", None)
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")

        frame.show_media(str(clip))

        assert frame._placeholder_label.isHidden() is False
        assert "clip.mp4" in frame._placeholder_label.text()
        assert frame.current_media_type() is MediaType.NONE
