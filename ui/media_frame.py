"""
Media frame (PySide6): images, animated images, and video.

Static images go through a QGraphicsView (pan/zoom, and one surface that can be
hidden wholesale when video takes over), animated rasters through QMovie, and
video through VLC embedded on this widget's native handle.

Unlike the reference implementations this was adapted from, no separate
playback engine owns the transport -- this frame owns its VLC player, so the
controls overlay's requests are handled here rather than re-emitted.
"""

import os
import platform
import threading
import time
import warnings
from enum import Enum, auto

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)
from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QImage, QImageReader, QMovie, QPainter, QPixmap

from ui.app_style import AppStyle
from ui.media_controls_overlay import MediaControlsOverlay, OVERLAY_HEIGHT
from utils.logging_setup import get_logger
from utils.translations import _

logger = get_logger(__name__)

# Formats Qt may not build in (HEIC, AVIF, ...). Optional: the frame degrades to
# whatever QImageReader handles.
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# The plugin-cache check runs first: a stale cache makes VLC load without any
# codecs, which fails later and less legibly than not importing at all.
#
# Every exception is caught, not just ImportError: python-vlc raises OSError
# when it cannot find libvlc, which is exactly the missing-runtime case this
# guard exists for. Letting it escape would take the whole ui package down at
# import, since ui/__init__.py imports this module.
try:
    from utils.vlc_plugin_cache import ensure_vlc_plugin_cache_if_stale

    ensure_vlc_plugin_cache_if_stale()
    import vlc
    _VLC_AVAILABLE = True
except Exception as _vlc_import_error:  # noqa: BLE001 - see above
    logger.warning(f"VLC is unavailable; video playback is disabled: {_vlc_import_error}")
    _VLC_AVAILABLE = False

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".webm", ".mov", ".m4v", ".ogv")

#: Extensions that *may* hold more than one frame. Membership only selects a
#: candidate; QImageReader decides, since most files with these extensions are
#: ordinary stills.
ANIMATED_EXTENSIONS = (".gif", ".webp", ".apng", ".png")

#: Containers whose stop() has been seen to hang. See video_stop().
MATROSKA_EXTENSIONS = (".mkv", ".webm")

PLAYBACK_TICK_MS = 250
MOUSE_POLL_MS = 100
VIDEO_STOP_TIMEOUT_S = 3.0

#: Paths whose stop() timed out once. Populated lazily, never cleared: a
#: container missing its seek index will hang the same way every time, so the
#: warning is shown from the second load on rather than re-earned each time.
_missing_seek_index_paths: set = set()


class MediaType(Enum):
    """What the frame is currently showing."""
    NONE = auto()
    IMAGE = auto()
    ANIMATED = auto()
    VIDEO = auto()


def scale_dims(dims, max_dims, maximize=False):
    """Return (width, height) fitting *dims* inside *max_dims*, aspect kept.

    Without *maximize*, something already smaller than the box is left alone;
    with it, that case is grown until one side meets the box.

    Both directions use the smaller of the two ratios, so the result always
    fits. Growing to meet one side without checking the other overflows the
    box for any image whose aspect ratio is the more extreme of the two -- a
    100x50 image in a 200x200 box becomes 400x200 -- which for the animated
    path means a cropped frame with no way to see the rest.
    """
    x, y = dims[0], dims[1]
    max_x, max_y = max_dims[0], max_dims[1]
    if x <= 0 or y <= 0:
        return (max(max_x, 1), max(max_y, 1))
    scale = min(max_x / x, max_y / y)
    if scale >= 1 and not maximize:
        return (x, y)
    return (max(1, int(x * scale)), max(1, int(y * scale)))


class MediaFrame(QFrame):
    """Display area for generated images and videos."""

    #: Marshals VLC's end-of-media callback onto the GUI thread. It fires on
    #: VLC's own event thread, which must not call back into VLC.
    _video_ended = Signal()

    def __init__(self, parent=None, fill_canvas=False):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        colors = AppStyle.get_theme_colors()
        self._media_bg = colors['media_bg']
        self.setStyleSheet(f"background-color: {self._media_bg};")

        self.fill_canvas = fill_canvas
        self.path = None
        self._media_type = MediaType.NONE
        # Held at full resolution: the view's SmoothPixmapTransform does the
        # downscale in one pass, so resizing never rescales an already-scaled
        # copy and compounds the loss.
        self._current_pixmap = None
        self._loop_video_path = None
        self._video_has_seek_index = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._graphics_view = QGraphicsView(self)
        self._graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._graphics_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._graphics_view.setStyleSheet(f"background-color: {self._media_bg};")
        self._scene = QGraphicsScene(self)
        self._graphics_view.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        layout.addWidget(self._graphics_view)

        self._animated_label = QLabel(self)
        self._animated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._animated_label.hide()
        layout.addWidget(self._animated_label)
        self._movie = None

        self._placeholder_label = QLabel("", self)
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet(f"color: {colors['text']};")
        self._placeholder_label.hide()
        layout.addWidget(self._placeholder_label)

        self._init_vlc()

        self._controls_overlay = MediaControlsOverlay(self)
        self._controls_overlay.seek_requested.connect(self._on_seek_requested)
        self._controls_overlay.play_pause_requested.connect(self._on_play_pause_requested)
        self._controls_overlay.volume_changed.connect(self._on_volume_requested)
        self._controls_overlay.mute_toggled.connect(self._on_mute_requested)
        self._window_filter_installed = False
        self._mouse_inside = False

        self._mouse_poll_timer = QTimer(self)
        self._mouse_poll_timer.setInterval(MOUSE_POLL_MS)
        self._mouse_poll_timer.timeout.connect(self._poll_mouse_position)
        self._mouse_poll_timer.start()

        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(PLAYBACK_TICK_MS)
        self._playback_timer.timeout.connect(self._update_playback_progress)

    def _init_vlc(self):
        if not _VLC_AVAILABLE:
            self.vlc_instance = None
            self.vlc_media_player = None
            self.vlc_media = None
            return
        self.vlc_instance = vlc.Instance()
        self.vlc_media_player = self.vlc_instance.media_player_new()
        # The overlay is the only transport UI; VLC's own input would fight it.
        self.vlc_media_player.video_set_mouse_input(False)
        self.vlc_media_player.video_set_key_input(False)
        self.vlc_media = None
        self._video_ended.connect(self._restart_looped_video)
        self.vlc_media_player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_media(self, path):
        """Display whatever *path* is: video, animated image, or still."""
        self._stop_current()
        self.path = path or None
        if not path or not str(path).strip() or not os.path.exists(path):
            self.clear()
            return

        if self._is_video(path):
            self._show_video(path)
            return
        if self._is_animated_candidate(path) and self._show_animated(path):
            return
        try:
            self._show_image(path)
        except Exception as e:
            logger.warning(f"Failed to render media {path}: {e}")
            self._show_placeholder(
                _("Unable to display this file: {0}").format(os.path.basename(path)))

    def show_pending(self, caption=None):
        """Show that media is on the way, before there is a file to display."""
        self._stop_current()
        self.path = None
        self._show_placeholder(caption or _("Generating..."))

    def clear(self):
        """Show nothing, keeping the frame ready for the next item."""
        self._stop_current()
        self.path = None
        self._scene.clear()
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._current_pixmap = None
        self._media_type = MediaType.NONE
        self._graphics_view.show()
        self._animated_label.hide()
        self._placeholder_label.hide()
        self._controls_overlay.on_playback_stopped()

    def release_media(self):
        """Drop decoded data and stop playback, for teardown.

        Qt does not deliver a close event to a non-window child, so a frame in
        a splitter never gets one -- the owning window calls this instead.
        """
        self._stop_current()
        self._mouse_poll_timer.stop()
        self._playback_timer.stop()
        self._controls_overlay.dismiss()
        self._current_pixmap = None
        self._pixmap_item.setPixmap(QPixmap())
        self._media_type = MediaType.NONE
        self._release_vlc()

    def _release_vlc(self):
        """Hand the player and instance back to libvlc.

        Safe to repeat: everything downstream checks for a player first, so a
        released frame simply reports that video is unavailable.
        """
        for name in ("vlc_media_player", "vlc_instance"):
            obj = getattr(self, name, None)
            if obj is None:
                continue
            try:
                obj.release()
            except Exception as e:
                logger.debug(f"Could not release {name}: {e}")
            setattr(self, name, None)

    def set_fill_canvas(self, fill_canvas):
        """Grow images smaller than the frame to fill it."""
        self.fill_canvas = bool(fill_canvas)
        if self._media_type == MediaType.IMAGE:
            self._apply_image_scale()
        elif self._media_type == MediaType.ANIMATED:
            self._update_animated_scale()

    def current_media_type(self):
        return self._media_type

    # ------------------------------------------------------------------
    # Type dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _is_video(path):
        return str(path).lower().endswith(VIDEO_EXTENSIONS)

    @staticmethod
    def _is_animated_candidate(path):
        return str(path).lower().endswith(ANIMATED_EXTENSIONS)

    # ------------------------------------------------------------------
    # Still images
    # ------------------------------------------------------------------

    def _load_image(self, path):
        """Decode *path*, falling back to Pillow for formats Qt lacks."""
        reader = QImageReader(path)
        image = reader.read()
        if not image.isNull():
            return image
        if not _PIL_AVAILABLE:
            return QImage()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                return self._load_image_via_pillow(path)
            except Exception as e:
                if "truncated" not in str(e):
                    raise
                # A file still being written by the generator. One retry is
                # enough to cover the gap between the last byte and the close.
                time.sleep(0.25)
                return self._load_image_via_pillow(path)

    @staticmethod
    def _load_image_via_pillow(path):
        pil_image = Image.open(path).convert("RGB")
        data = pil_image.tobytes("raw", "RGB")
        return QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGB888)

    def _show_image(self, path):
        image = self._load_image(path)
        if image.isNull():
            self._show_placeholder(
                _("Unable to display this file: {0}").format(os.path.basename(path)))
            return
        self._current_pixmap = QPixmap.fromImage(image)
        self._pixmap_item.setPixmap(self._current_pixmap)
        self._scene.setSceneRect(QRectF(self._current_pixmap.rect()))
        self._apply_image_scale()
        self._media_type = MediaType.IMAGE
        self._graphics_view.show()
        self._animated_label.hide()
        self._placeholder_label.hide()

    def _apply_image_scale(self):
        """Fit the view to the image, or leave it 1:1 when it already fits."""
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        viewport = self._graphics_view.viewport().size()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        oversized = (
            self._current_pixmap.width() > viewport.width()
            or self._current_pixmap.height() > viewport.height()
        )
        if self.fill_canvas or oversized:
            self._graphics_view.fitInView(
                self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self._graphics_view.resetTransform()

    # ------------------------------------------------------------------
    # Animated images
    # ------------------------------------------------------------------

    @staticmethod
    def _is_animated(path):
        """Whether *path* holds more than one frame.

        Only the yes/no answer is needed, and every .png is a candidate here,
        so this must not decode a whole file to find out: imageCount() answers
        from the header where the plugin supports it, and the fallback stops at
        the second frame.
        """
        reader = QImageReader(path)
        if not reader.supportsAnimation():
            return False
        count = reader.imageCount()
        if count > 0:
            return count > 1
        frames = 0
        while frames < 2:
            if reader.read().isNull():
                break
            frames += 1
            if not reader.canRead():
                break
        return frames > 1

    def _show_animated(self, path):
        """Play *path* as an animation. False when it holds only one frame."""
        if not self._is_animated(path):
            return False
        movie = QMovie(path)
        if not movie.isValid():
            self._show_placeholder(
                _("Cannot play this animated file: {0}").format(os.path.basename(path)))
            return True
        self._movie = movie
        self._animated_label.setMovie(movie)
        self._graphics_view.hide()
        self._placeholder_label.hide()
        self._animated_label.show()
        self._update_animated_scale()
        movie.start()
        # Re-scale once layout has settled: on the first animation the label can
        # still report its pre-layout size, which would lock the movie too small.
        QTimer.singleShot(0, self._update_animated_scale)
        self._media_type = MediaType.ANIMATED
        # No audio track, and no reliable duration without walking every frame
        # delay, so the transport has nothing useful to offer.
        self._controls_overlay.set_audio_controls_visible(False)
        return True

    def _update_animated_scale(self):
        if self._movie is None:
            return
        frame = self._movie.frameRect().size()
        if frame.width() <= 0 or frame.height() <= 0:
            return
        label_w = max(self._animated_label.width(), self.contentsRect().width(), 1)
        label_h = max(self._animated_label.height(), self.contentsRect().height(), 1)
        width, height = scale_dims(
            (frame.width(), frame.height()), (label_w, label_h),
            maximize=self.fill_canvas,
        )
        if (width, height) == (frame.width(), frame.height()):
            self._movie.setScaledSize(QSize())
        else:
            self._movie.setScaledSize(QSize(width, height))

    def _teardown_movie(self):
        """Detach and release the QMovie so the file is not left locked."""
        movie = self._movie or self._animated_label.movie()
        if movie is None:
            self._movie = None
            return
        try:
            movie.stop()
            self._animated_label.setMovie(None)
        except Exception as e:
            logger.debug(f"Could not detach movie cleanly: {e}")
        self._movie = None
        self._animated_label.clear()

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    def _show_video(self, path, loop=False):
        """Play *path* through VLC, embedded on this widget's handle."""
        if not _VLC_AVAILABLE or self.vlc_media_player is None:
            self._show_placeholder(
                _("Video playback is unavailable: {0}").format(os.path.basename(path)))
            return False
        self._graphics_view.hide()
        self._animated_label.hide()
        self._placeholder_label.hide()
        self.ensure_video_frame()

        self.vlc_media = self.vlc_instance.media_new(path)
        if loop:
            # Ignored by some VLC builds, which is what _restart_looped_video
            # covers -- both are needed, neither alone is reliable.
            self.vlc_media.add_option("input-repeat=65535")
        self._loop_video_path = path if loop else None
        self.vlc_media_player.set_media(self.vlc_media)
        if self.vlc_media_player.play() == -1:
            self._loop_video_path = None
            logger.warning(f"VLC refused to play {path}")
            self._show_placeholder(
                _("Could not play this video: {0}").format(os.path.basename(path)))
            return False

        self._media_type = MediaType.VIDEO
        self._video_has_seek_index = path not in _missing_seek_index_paths
        self._controls_overlay.set_audio_controls_visible(True)
        self._controls_overlay.set_no_seek_index(not self._video_has_seek_index)
        self._controls_overlay.on_track_changed()
        self._sync_volume_state()
        self._playback_timer.start()
        return True

    def play_video_looped(self, path):
        """Show *path* and repeat it until something else is displayed."""
        self._stop_current()
        self.path = path
        return self._show_video(path, loop=True)

    def ensure_video_frame(self):
        """Point VLC's video output at this widget's native handle."""
        if not _VLC_AVAILABLE or self.vlc_media_player is None:
            return
        handle = int(self.winId()) if self.winId() else 0
        if not handle:
            return
        system = platform.system()
        if system == "Windows":
            self.vlc_media_player.set_hwnd(handle)
        elif system == "Darwin":
            self.vlc_media_player.set_nsobject(handle)
        else:
            self.vlc_media_player.set_xwindow(handle)

    def _on_vlc_end_reached(self, event):
        """Runs on VLC's event thread, which must not call back into VLC."""
        if self._loop_video_path is not None:
            self._video_ended.emit()

    def _restart_looped_video(self):
        path = self._loop_video_path
        if path is None:
            return
        try:
            self._show_video(path, loop=True)
        except Exception as e:
            logger.warning(f"Could not restart looped video {path}: {e}")

    def video_stop(self):
        """Stop playback, surviving a libvlc stop() that never returns.

        libvlc_media_player_stop() is synchronous in libvlc 3.x: it blocks
        until the decode loop exits. For a container with no seek index that
        loop can stall indefinitely and take the GUI thread with it, so it runs
        on a daemon thread; if it hangs, the player is abandoned for a fresh
        one and the path is remembered so its next load warns up front.
        """
        self._playback_timer.stop()
        self._loop_video_path = None
        if _VLC_AVAILABLE and self.vlc_media_player is not None:
            player = self.vlc_media_player
            stopper = threading.Thread(target=player.stop, daemon=True)
            stopper.start()
            stopper.join(timeout=VIDEO_STOP_TIMEOUT_S)
            if stopper.is_alive():
                logger.warning(
                    f"VLC stop() timed out for {self.path}; abandoning the player")
                if self.path and str(self.path).lower().endswith(MATROSKA_EXTENSIONS):
                    _missing_seek_index_paths.add(self.path)
                self._replace_vlc_player()
            else:
                try:
                    player.set_media(None)
                except Exception as e:
                    logger.debug(f"Could not detach VLC media: {e}")
        if self.vlc_media is not None:
            try:
                self.vlc_media.release()
            except Exception as e:
                logger.debug(f"Could not release VLC media: {e}")
            self.vlc_media = None
        if self._media_type == MediaType.VIDEO:
            self._media_type = MediaType.NONE
        self._controls_overlay.on_playback_stopped()

    def _replace_vlc_player(self):
        """Build a fresh player after the previous one failed to stop."""
        try:
            player = self.vlc_instance.media_player_new()
            player.video_set_mouse_input(False)
            player.video_set_key_input(False)
            self.vlc_media_player = player
        except Exception as e:
            logger.error(f"Could not replace the VLC player: {e}")
            self.vlc_media_player = None

    # ------------------------------------------------------------------
    # Transport, driven by the overlay
    # ------------------------------------------------------------------

    def _playing_video(self):
        return (
            _VLC_AVAILABLE
            and self.vlc_media_player is not None
            and self._media_type == MediaType.VIDEO
        )

    def _on_seek_requested(self, position_ms):
        if self._playing_video() and self._video_has_seek_index:
            self.vlc_media_player.set_time(int(position_ms))

    def _on_play_pause_requested(self):
        if not self._playing_video():
            return
        self.vlc_media_player.pause()   # toggles
        self._controls_overlay.set_paused(not self.vlc_media_player.is_playing())

    def _on_volume_requested(self, volume):
        if self._playing_video():
            self.vlc_media_player.audio_set_volume(int(volume))
            self._sync_volume_state()

    def _on_mute_requested(self):
        if not self._playing_video():
            return
        self.vlc_media_player.audio_set_mute(not self.vlc_media_player.audio_get_mute())
        self._sync_volume_state()

    def _sync_volume_state(self):
        if not self._playing_video():
            return
        volume = self.vlc_media_player.audio_get_volume()
        muted = bool(self.vlc_media_player.audio_get_mute())
        # VLC reports -1 for volume before playback has really begun.
        self._controls_overlay.set_volume_state(max(volume, 0), muted)

    def _update_playback_progress(self):
        if not self._playing_video():
            self._playback_timer.stop()
            return
        current = self.vlc_media_player.get_time()
        duration = self.vlc_media_player.get_length()
        # A duration of 0 means VLC has not parsed it yet; -1 tells the overlay
        # to show an unknown length rather than a bogus 0:00 total.
        self._controls_overlay.update_progress(
            max(current, 0), duration if duration > 0 else -1)
        self._controls_overlay.set_paused(not self.vlc_media_player.is_playing())

    # ------------------------------------------------------------------
    # Shared state handling
    # ------------------------------------------------------------------

    def _stop_current(self):
        """Tear down whatever is playing, leaving the surfaces alone."""
        if self._media_type == MediaType.VIDEO:
            self.video_stop()
        if self._movie is not None:
            self._teardown_movie()

    def _show_placeholder(self, text):
        self._stop_current()
        self._graphics_view.hide()
        self._animated_label.hide()
        self._placeholder_label.setText(text)
        self._placeholder_label.show()
        self._media_type = MediaType.NONE
        self._controls_overlay.on_playback_stopped()

    # ------------------------------------------------------------------
    # Geometry and the overlay's visibility
    # ------------------------------------------------------------------

    def _position_overlay(self):
        """Place the overlay along the bottom of the frame, in global coords.

        Global rather than local because the overlay is a top-level window --
        that is what lets it paint above VLC's native video surface.
        """
        bottom_left = self.mapToGlobal(QPoint(0, self.height() - OVERLAY_HEIGHT))
        self._controls_overlay.setGeometry(
            bottom_left.x(), bottom_left.y(), self.width(), OVERLAY_HEIGHT)

    def _ensure_window_filter(self):
        """Track the top-level window so the overlay follows it when it moves."""
        if self._window_filter_installed:
            return
        window = self.window()
        if window is not None and window is not self:
            window.installEventFilter(self)
            self._window_filter_installed = True

    def eventFilter(self, watched, event):
        if event.type() in (
            QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange
        ):
            self._position_overlay()
        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_overlay()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_window_filter()
        self._position_overlay()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._mouse_inside = False
        self._controls_overlay.dismiss()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_overlay()
        if self._media_type == MediaType.IMAGE:
            self._apply_image_scale()
        elif self._media_type == MediaType.ANIMATED:
            self._update_animated_scale()

    def _has_time_based_media(self):
        return self._media_type in (MediaType.VIDEO, MediaType.ANIMATED)

    def _poll_mouse_position(self):
        """Drive overlay visibility from the cursor position.

        VLC's native video output swallows mouse events, so enterEvent and
        leaveEvent never fire over video. Comparing the cursor against this
        widget's screen rect is what works for both surfaces.
        """
        if not self.isVisible() or not self._has_time_based_media():
            return
        app = QApplication.instance()
        window = self.window()
        if app is None or window is None:
            return
        if app.activeWindow() is not window or self._has_visible_child_dialog(window):
            self._mouse_inside = False
            self._controls_overlay.dismiss()
            return

        cursor = QCursor.pos()
        frame_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        inside = frame_rect.contains(cursor) or self._controls_overlay.geometry().contains(cursor)
        if inside and not self._mouse_inside:
            self._mouse_inside = True
            self._position_overlay()
            self._controls_overlay.show_overlay()
        elif not inside and self._mouse_inside:
            self._mouse_inside = False
            self._controls_overlay.hide_overlay()

    def _has_visible_child_dialog(self, window):
        """Whether a dialog belonging to *window* is open.

        The overlay is a top-level window, so it does not stack behind a modal
        dialog on its own.
        """
        app = QApplication.instance()
        if app is None or window is None:
            return False
        for widget in app.topLevelWidgets():
            if widget is window or widget is self._controls_overlay:
                continue
            if not widget.isVisible() or not isinstance(widget, QDialog):
                continue
            parent = widget.parentWidget()
            while parent is not None:
                if parent is window:
                    return True
                parent = parent.parentWidget()
        return False
