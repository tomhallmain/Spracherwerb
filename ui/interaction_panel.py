from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from utils.config import config

class InteractionPanel(QWidget):
    """Right sidebar for user interaction with the language agent"""
    def __init__(self, parent=None, session_controller=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.session_controller = session_controller
        
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
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {config.background_color};
                color: {config.foreground_color};
                border: 1px solid #3a3a3a;
                padding: 5px;
            }}
        """)
        
        self.send_button = QPushButton("Send")
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
        if is_html:
            self.log_area.append(f"<b>{sender}:</b><br>{content}")
        else:
            self.log_area.append(f"<b>{sender}:</b><br>{content}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
    def append_media_message(self, sender, media_path, media_type="image", caption=None):
        """Append a message containing media to the log area"""
        if media_type == "image":
            pixmap = QPixmap(media_path)
            if not pixmap.isNull():
                # Convert pixmap to base64 for HTML display
                import base64
                from io import BytesIO
                buffer = BytesIO()
                pixmap.save(buffer, "PNG")
                img_str = base64.b64encode(buffer.getvalue()).decode()
                
                # Create HTML content with image
                html_content = f'<img src="data:image/png;base64,{img_str}" style="max-width: 100%;">'
                if caption:
                    html_content += f'<br><i>{caption}</i>'
                
                self.append_message(sender, html_content, is_html=True)
        # TODO: Add support for video when MediaFrame is ready
        
    def send_message(self):
        """Handle sending messages to the language agent"""
        message = self.input_field.text()
        if not message:
            return
        self.append_message("You", message)
        self.input_field.clear()

        if self.session_controller is None or not self.session_controller.has_active_activity():
            self.append_message("Agent", "Select a learning mode to begin.")
            return

        try:
            result = self.session_controller.send_message(message)
        except Exception as e:
            self.append_message("Agent", f"Error: {e}")
            return
        self._render_turn_result(result)

    def start_activity(self, activity_type):
        """Start (or switch to) an activity and show its opening message."""
        if self.session_controller is None:
            return
        try:
            result = self.session_controller.start_activity(activity_type)
        except Exception as e:
            self.append_message("Agent", f"Error starting activity: {e}")
            return
        self._render_turn_result(result)

    def _render_turn_result(self, result):
        """Render an ActivityStartResult/ActivityTurnResult dict into the log."""
        text = result.get('text_response')
        if text:
            self.append_message("Agent", text)
        media_path = result.get('media_path')
        if media_path:
            self.append_media_message("Agent", media_path)