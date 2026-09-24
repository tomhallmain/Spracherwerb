import html
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal, Slot

from Spracherwerb.media_generation import MediaPriority, MediaState
from utils.config import config
from utils.translations import _
from utils.utils import Utils

class InteractionPanel(QWidget):
    """Right sidebar for user interaction with the language agent"""
    # Signal emitted with a file path whenever an activity turn includes media,
    # so MainWindow can route it to the dedicated MediaFrame panel.
    media_ready = Signal(str)

    # Worker thread -> GUI thread. A turn runs off the GUI thread, and Qt
    # queues a signal emitted from another thread onto the receiver's thread,
    # which is the only safe way back to the widgets. The int is the request
    # id; see _finish_turn for what a stale one means.
    _turn_succeeded = Signal(int, object)
    _turn_failed = Signal(int, str)

    # Media generation, for the frame. Emitted while a turn waits on a picture
    # and when that picture turns out not to be coming.
    media_pending = Signal(str)
    media_unavailable = Signal()

    # Generation events arrive on the generation worker's thread; this carries
    # them to the GUI thread, same as the turn signals above.
    _media_event = Signal(object)

    def __init__(self, parent=None, session_controller=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.session_controller = session_controller

        self._request_counter = 0
        self._active_request_id = None   # id of the turn whose result is wanted
        self._pending_work = None        # at most one turn waiting to start
        self._busy = False
        self._turn_succeeded.connect(self._on_turn_succeeded)
        self._turn_failed.connect(self._on_turn_failed)
        self._media_event.connect(self._on_media_event)
        
        # Create layout
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # Interaction log with HTML support
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setAcceptRichText(True)  # Enable HTML content
        self.log_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {config.background_color};
                color: {config.foreground_color};
                border: 1px solid #3a3a3a;
            }}
        """)
        layout.addWidget(self.log_area)
        
        # User input area
        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(_("Type your message here..."))
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {config.background_color};
                color: {config.foreground_color};
                border: 1px solid #3a3a3a;
                padding: 5px;
            }}
        """)
        
        self.send_button = QPushButton(_("Send"))
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: {config.foreground_color};
                border: 1px solid #3a3a3a;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        layout.addWidget(input_frame)
        
    def append_message(self, sender, content, is_html=False):
        """Append a message to the log area with optional HTML content"""
        # The log is rich text, so plain content (LLM output included) is
        # escaped: a "<" in it would otherwise be parsed as markup.
        if not is_html:
            content = html.escape(content).replace("\n", "<br>")
        self.log_area.append(f"<b>{html.escape(sender)}:</b><br>{content}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
    def append_media_notice(self, sender, media_path):
        """Note in the log that media was produced; the frame displays it.

        The name only. Inlining the image would hold a second full-resolution
        copy of every one for the life of the session, in a log that only
        grows, and the frame beside it is already showing the thing.
        """
        self.append_message(
            sender, _("[shared: {0}]").format(os.path.basename(media_path)))

    
    def send_message(self):
        """Handle sending messages to the language agent"""
        message = self.input_field.text()
        if not message:
            return
        self.append_message(_("You"), message)
        self.input_field.clear()

        if self.session_controller is None or not self.session_controller.has_active_activity():
            self.append_message(_("Agent"), _("Select a learning mode to begin."))
            return

        self._begin_turn(
            lambda: self.session_controller.send_message(message),
            _("Error: {0}"),
        )

    def start_activity(self, activity_type):
        """Start (or switch to) an activity and show its opening message."""
        if self.session_controller is None:
            return
        self._begin_turn(
            lambda: self.session_controller.start_activity(activity_type),
            _("Error starting activity: {0}"),
        )

    # ------------------------------------------------------------------
    # Turn execution
    #
    # A turn can take minutes: a module that needs an image calls
    # SDRunnerClient.generate_image(), which polls for the generated file up
    # to its timeout. Run on the GUI thread that stops every repaint and
    # keystroke for the duration, so turns run on a worker and come back
    # through _turn_succeeded / _turn_failed.
    #
    # The turn state below (_busy, _pending_work, _active_request_id) is
    # touched only from the GUI thread -- the worker holds nothing but its own
    # request id -- so none of it is locked.
    # ------------------------------------------------------------------

    def _begin_turn(self, work, error_template):
        """Run *work* as the next turn, or queue it if one is in flight.

        Only one turn runs at a time. They share the SessionController's
        single session, and two threads inside one learning module would race
        on its per-activity state. A turn already running when another is
        requested is left to finish rather than interrupted mid-call, but its
        result is discarded -- the user has moved on from it.
        """
        if self._busy:
            self._pending_work = (work, error_template)
            self._active_request_id = None
            return
        self._start_turn(work, error_template)

    def _start_turn(self, work, error_template):
        self._busy = True
        self._request_counter += 1
        request_id = self._request_counter
        self._active_request_id = request_id
        self._set_input_enabled(False)

        def run_turn():
            try:
                result = work()
            except Exception as e:
                # Formatted here so the message travels with the signal; an
                # instance attribute would be overwritten by the next turn.
                self._emit_turn_signal(
                    self._turn_failed, request_id, error_template.format(e))
                return
            self._emit_turn_signal(self._turn_succeeded, request_id, result)

        Utils.start_thread(run_turn, use_asyncio=False)

    def _emit_turn_signal(self, signal, request_id, payload):
        """Emit a worker result, tolerating a panel torn down mid-turn.

        The worker is a daemon thread holding a reference to this widget, so
        a turn still running when the window closes would emit on a deleted
        C++ object.
        """
        try:
            signal.emit(request_id, payload)
        except RuntimeError:
            pass

    @Slot(int, object)
    def _on_turn_succeeded(self, request_id, result):
        if self._finish_turn(request_id):
            self._render_turn_result(result)

    @Slot(int, str)
    def _on_turn_failed(self, request_id, message):
        if self._finish_turn(request_id):
            self.append_message(_("Agent"), message)

    def _finish_turn(self, request_id):
        """Clear the busy state, start any queued turn, and report whether
        *request_id*'s result is still wanted.

        A stale id means the turn was superseded while it ran, so its result
        describes a state the user has already left.
        """
        wanted = request_id == self._active_request_id
        self._busy = False
        pending, self._pending_work = self._pending_work, None
        if pending is not None:
            self._start_turn(*pending)
        else:
            self._active_request_id = None
            self._set_input_enabled(True)
        return wanted

    def _set_input_enabled(self, enabled):
        """Enable or disable user input while a turn is in flight."""
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.input_field.setPlaceholderText(
            _("Type your message here...") if enabled else _("Working...")
        )

    def handle_media_event(self, event):
        """Take a generation event from the worker onto the GUI thread.

        Registered with SessionController; see _on_media_event for what is
        done with it.
        """
        try:
            self._media_event.emit(event)
        except RuntimeError:
            pass

    @Slot(object)
    def _on_media_event(self, event):
        """Show progress for the picture this turn is waiting on.

        Only while a turn is in flight, and only for the item being waited on:
        a picture drawn ahead of time must not put "generating" over the one
        already on screen, and an event arriving after the turn has finished
        describes a state the frame has moved past.
        """
        if not self._busy or event.priority is not MediaPriority.NOW:
            return
        if event.state is MediaState.RUNNING:
            self.media_pending.emit(_("Generating..."))
        elif event.state in (MediaState.FAILED, MediaState.CANCELLED):
            # Nothing further is coming, and the frame is showing a
            # placeholder that would otherwise stay up for good.
            self.media_unavailable.emit()

    def _render_turn_result(self, result):
        """Render an ActivityStartResult/ActivityTurnResult dict into the log."""
        text = result.get('text_response')
        if text:
            self.append_message(_("Agent"), text)
        media_path = result.get('media_path')
        if media_path:
            self.append_media_notice(_("Agent"), media_path)
            self.media_ready.emit(media_path)