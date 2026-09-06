"""
Media controls overlay (PySide6): translucent bar with seek slider,
play/pause button, and elapsed/total time labels. Sits at the bottom
of MediaFrame and auto-hides after a period of mouse inactivity.

Implemented as a top-level Tool window with WA_TranslucentBackground so it
has its own native handle and renders above VLC's DirectX/OpenGL surface.
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QPainter, QColor

from ui.app_style import AppStyle
from utils.translations import I18N

_ = I18N._


SLIDER_MAX = 1000
VOLUME_MAX = 100
AUTOHIDE_MS = 3000
FADE_IN_MS = 200
FADE_OUT_MS = 500
OVERLAY_HEIGHT = 44
MUTE_ICON = "\U0001F507"
UNMUTE_ICON = "\U0001F50A"
PLAY_ICON = "▶"
PAUSE_ICON = "❚❚"
WARNING_ICON = "⚠"

#: The bar's own background. Painted rather than styled so the alpha survives:
#: a stylesheet background on a translucent top-level window is composited
#: differently across platforms.
BACKGROUND_COLOR = QColor(10, 22, 40, 180)


def _fmt_time(ms: int) -> str:
    """Format milliseconds as m:ss or h:mm:ss."""
    if ms < 0:
        ms = 0
    total_secs = ms // 1000
    h = total_secs // 3600
    m = (total_secs % 3600) // 60
    s = total_secs % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class MediaControlsOverlay(QWidget):
    """Translucent controls bar rendered over the bottom of the media frame.

    A top-level Tool window so it floats above VLC's native video surface
    and disappears with the parent window on alt-tab / minimize.
    """

    seek_requested = Signal(int)
    play_pause_requested = Signal()
    volume_changed = Signal(int)
    mute_toggled = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowOpacity(0.0)

        self._is_paused = False
        self._user_is_seeking = False
        self._duration_ms = 0
        self._current_ms = 0
        self._has_track = False
        self._volume = VOLUME_MAX
        self._is_muted = False

        colors = AppStyle.get_theme_colors()
        self._border_color = QColor(colors['highlight'])

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)

        self._autohide_timer = QTimer(self)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self._fade_out)

        self._build_ui()
        self._apply_child_styles()

    # ------------------------------------------------------------------
    # Paint the semi-transparent background ourselves
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BACKGROUND_COLOR)
        p.setPen(self._border_color)
        p.drawLine(0, 0, self.width(), 0)
        p.end()

    # ------------------------------------------------------------------
    # Build child widgets
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self._play_pause_btn = QPushButton(PLAY_ICON, self)
        self._play_pause_btn.setFixedSize(32, 32)
        self._play_pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._play_pause_btn.clicked.connect(self._on_play_pause)
        layout.addWidget(self._play_pause_btn)

        self._elapsed_label = QLabel("0:00", self)
        self._elapsed_label.setFixedWidth(52)
        self._elapsed_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._elapsed_label)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._seek_slider.setRange(0, SLIDER_MAX)
        self._seek_slider.setValue(0)
        self._seek_slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)
        self._seek_slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self._seek_slider)

        self._total_label = QLabel("0:00", self)
        self._total_label.setFixedWidth(52)
        self._total_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._total_label)

        self._no_seek_label = QLabel(f"{WARNING_ICON} " + _("No seek index"), self)
        self._no_seek_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._no_seek_label.hide()
        layout.addWidget(self._no_seek_label)

        self._mute_btn = QPushButton(MUTE_ICON, self)
        self._mute_btn.setFixedSize(32, 32)
        self._mute_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mute_btn.clicked.connect(self._on_mute_toggle)
        layout.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._volume_slider.setRange(0, VOLUME_MAX)
        self._volume_slider.setValue(self._volume)
        self._volume_slider.setFixedWidth(90)
        self._volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self._volume_slider)

    def _apply_child_styles(self):
        colors = AppStyle.get_theme_colors()
        btn_style = (
            f"QPushButton {{"
            f"  background: transparent; color: {colors['text']};"
            f"  border: 1px solid {colors['highlight']}; border-radius: 4px;"
            f"  font-size: 14px;"
            f"}}"
            f"QPushButton:hover {{ background: {colors['highlight']}; }}"
        )
        self._play_pause_btn.setStyleSheet(btn_style)
        self._mute_btn.setStyleSheet(btn_style)

        label_style = (
            f"color: {colors['text']}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        self._elapsed_label.setStyleSheet(label_style)
        self._total_label.setStyleSheet(label_style)
        self._no_seek_label.setStyleSheet(
            f"color: {AppStyle.Colors.WARNING}; font-size: 11px; "
            f"background: transparent; border: none;"
        )

        slider_style = (
            f"QSlider::groove:horizontal {{"
            f"  border: 1px solid {colors['highlight']}; height: 4px;"
            f"  background: {colors['accent']}; border-radius: 2px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {AppStyle.Colors.PRIMARY};"
            f"  border: 1px solid {colors['highlight']};"
            f"  width: 12px; margin: -4px 0; border-radius: 6px;"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background: {colors['highlight']};"
            f"}}"
            f"QSlider::sub-page:horizontal {{"
            f"  background: {AppStyle.Colors.PRIMARY}; border-radius: 2px;"
            f"}}"
        )
        self._seek_slider.setStyleSheet(slider_style)
        self._volume_slider.setStyleSheet(slider_style)
        self._refresh_play_pause_button()
        self._refresh_mute_button()

    # ------------------------------------------------------------------
    # Public API (called by MediaFrame)
    # ------------------------------------------------------------------

    def update_progress(self, current_ms: int, duration_ms: int):
        """Called on every progress tick.

        A ``duration_ms`` of -1 is the sentinel for media of unknown length:
        the seek slider is frozen and the total label shows a dash.
        """
        is_open_ended = duration_ms < 0
        self._current_ms = current_ms
        self._duration_ms = 0 if is_open_ended else duration_ms
        self._has_track = is_open_ended or duration_ms > 0
        self._refresh_play_pause_button()

        if not self._user_is_seeking:
            if is_open_ended:
                self._seek_slider.setValue(0)
            else:
                pos = int((current_ms / duration_ms) * SLIDER_MAX) if duration_ms > 0 else 0
                self._seek_slider.setValue(pos)

        self._elapsed_label.setText(_fmt_time(current_ms))
        self._total_label.setText("--:--" if is_open_ended else _fmt_time(duration_ms))

    def set_paused(self, paused: bool):
        self._is_paused = paused
        self._refresh_play_pause_button()

    def on_track_changed(self):
        """Reset state when new media starts."""
        self._seek_slider.setValue(0)
        self._elapsed_label.setText("0:00")
        self._total_label.setText("0:00")
        self._is_paused = False
        self._has_track = True
        self._refresh_play_pause_button()

    def on_playback_stopped(self):
        """Reset state when nothing is playing."""
        self._has_track = False
        self._is_paused = False
        self._refresh_play_pause_button()
        self._seek_slider.setValue(0)
        self._elapsed_label.setText("0:00")
        self._total_label.setText("0:00")
        self.dismiss()

    def set_volume_state(self, volume: int, muted: bool):
        bounded = max(0, min(int(volume), VOLUME_MAX))
        self._volume = bounded
        self._is_muted = bool(muted)
        self._volume_slider.blockSignals(True)
        self._volume_slider.setValue(bounded)
        self._volume_slider.blockSignals(False)
        self._refresh_mute_button()

    def set_audio_controls_visible(self, visible: bool):
        """Show or hide the mute and volume controls.

        Hidden for media with no audio track, such as an animated image.
        """
        is_visible = bool(visible)
        self._mute_btn.setVisible(is_visible)
        self._mute_btn.setEnabled(is_visible)
        self._volume_slider.setVisible(is_visible)
        self._volume_slider.setEnabled(is_visible)

    def set_no_seek_index(self, active: bool):
        """Warn and disable seeking for a container with no seek index.

        A file without one has no way to jump to a position, so a slider that
        still moved would silently do nothing.
        """
        self._no_seek_label.setVisible(bool(active))
        self._seek_slider.setEnabled(not active)
        self._seek_slider.setToolTip(
            _("Seeking unavailable -- this file has no seek index") if active else ""
        )

    # ------------------------------------------------------------------
    # Visibility / auto-hide
    # ------------------------------------------------------------------

    def show_overlay(self):
        if not self._has_track:
            return
        self.show()
        self._fade_in()
        self._restart_autohide()

    def hide_overlay(self):
        self._autohide_timer.stop()
        self._fade_out()

    def dismiss(self):
        """Immediately hide without animation (e.g. parent hidden)."""
        self._autohide_timer.stop()
        self._fade_anim.stop()
        self.setWindowOpacity(0.0)
        self.hide()

    def _fade_in(self):
        self._fade_anim.stop()
        self._fade_anim.setDuration(FADE_IN_MS)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _fade_out(self):
        if self._user_is_seeking:
            return
        self._fade_anim.stop()
        self._fade_anim.setDuration(FADE_OUT_MS)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self):
        if self.windowOpacity() < 0.01:
            self.hide()

    def _restart_autohide(self):
        self._autohide_timer.stop()
        self._autohide_timer.start(AUTOHIDE_MS)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_play_pause(self):
        self._restart_autohide()
        self.play_pause_requested.emit()

    def _on_slider_pressed(self):
        self._user_is_seeking = True
        self._autohide_timer.stop()

    def _on_slider_released(self):
        self._user_is_seeking = False
        self._restart_autohide()
        if self._duration_ms > 0:
            ratio = self._seek_slider.value() / SLIDER_MAX
            self.seek_requested.emit(int(ratio * self._duration_ms))

    def _on_slider_moved(self, value: int):
        """Live preview of elapsed time while dragging; also seek-while-paused."""
        if self._duration_ms > 0:
            preview_ms = int((value / SLIDER_MAX) * self._duration_ms)
            self._elapsed_label.setText(_fmt_time(preview_ms))
            if self._is_paused:
                self.seek_requested.emit(preview_ms)

    def _on_volume_changed(self, value: int):
        self._restart_autohide()
        self.volume_changed.emit(int(value))

    def _on_mute_toggle(self):
        self._restart_autohide()
        self.mute_toggled.emit()

    def _refresh_mute_button(self):
        self._mute_btn.setText(UNMUTE_ICON if self._is_muted else MUTE_ICON)
        self._mute_btn.setToolTip(_("Unmute") if self._is_muted else _("Mute"))

    def _refresh_play_pause_button(self):
        is_playing = self._has_track and not self._is_paused
        self._play_pause_btn.setText(PAUSE_ICON if is_playing else PLAY_ICON)
        self._play_pause_btn.setToolTip(_("Pause") if is_playing else _("Play"))

    # ------------------------------------------------------------------
    # Mouse events (keep overlay visible while interacting)
    # ------------------------------------------------------------------

    def enterEvent(self, event):
        super().enterEvent(event)
        self._autohide_timer.stop()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if not self._user_is_seeking:
            self._restart_autohide()
