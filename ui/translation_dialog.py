from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTextEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
import traceback

from utils.config import config
from utils.globals import Language
from utils.translations import I18N

class CustomTextEdit(QTextEdit):
    def find_next_input_widget(self, forward=True):
        """Find the next or previous input widget in the dialog, skipping internal widgets
        
        Args:
            forward (bool): If True, find next widget; if False, find previous widget
        """
        current = self
        dialog = self.window()  # Get the top-level dialog
        
        # Get all input widgets in order
        input_widgets = [
            dialog._source_text_edit,
            dialog._translated_text_edit,
            dialog._notes_edit,
            dialog.add_button,
            dialog.cancel_button
        ]
        
        # Find current widget's index
        try:
            current_index = input_widgets.index(current)
            if forward:
                # Return next widget, wrapping around if needed
                return input_widgets[(current_index + 1) % len(input_widgets)]
            else:
                # Return previous widget, wrapping around if needed
                return input_widgets[(current_index - 1) % len(input_widgets)]
        except ValueError:
            return None

    def keyPressEvent(self, event: QKeyEvent):
        # Handle Ctrl+Enter to accept
        if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            dialog = self.window()
            if dialog.validate_inputs():
                dialog.accept()
            event.accept()
            return
            
        # Handle Shift+Escape to cancel
        if event.key() == Qt.Key_Escape and event.modifiers() & Qt.ShiftModifier:
            dialog = self.window()
            dialog.reject()
            event.accept()
            return
            
        # Handle Tab navigation and insertion
        is_shift_tab = event.key() == 16777218  # Shift+Tab key code
        if event.key() == Qt.Key_Tab or is_shift_tab:
            raw_modifiers = event.modifiers()
            shift_pressed = is_shift_tab or bool(raw_modifiers & Qt.ShiftModifier)
            ctrl_pressed = bool(raw_modifiers & Qt.ControlModifier)
            
            if ctrl_pressed and not shift_pressed:
                # If Ctrl is pressed without Shift, insert a tab character
                self.insertPlainText('\t')
            else:
                # Otherwise, move focus to next/previous widget
                try:
                    next_widget = self.find_next_input_widget(forward=not shift_pressed)
                    if next_widget:
                        next_widget.setFocus()
                    else:
                        print("No next widget found")
                except Exception as e:
                    print(f"Error in tab navigation: {e}")
                    traceback.print_exc()
            event.accept()
        else:
            super().keyPressEvent(event)

class TranslationDialog(QDialog):
    def __init__(self, parent=None, translation=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Translation" if translation else "Add Translation")
        self.setMinimumSize(400, 300)
        
        # Create main layout
        layout = QVBoxLayout(self)
        
        # Create language display
        language_layout = QHBoxLayout()
        self.source_language_label = QLabel(f"Source: {Language.get_language_name(config.source_language)}")
        self.target_language_label = QLabel(f"Target: {Language.get_language_name(config.target_language)}")
        language_layout.addWidget(self.source_language_label)
        language_layout.addWidget(self.target_language_label)
        layout.addLayout(language_layout)
        
        # Create source text input
        layout.addWidget(QLabel("Source Text:"))
        self._source_text_edit = CustomTextEdit()
        self._source_text_edit.setMaximumHeight(100)
        layout.addWidget(self._source_text_edit)
        
        # Create translated text input
        layout.addWidget(QLabel("Translated Text:"))
        self._translated_text_edit = CustomTextEdit()
        self._translated_text_edit.setMaximumHeight(100)
        layout.addWidget(self._translated_text_edit)
        
        # Create notes input
        layout.addWidget(QLabel("Notes (Optional):"))
        self._notes_edit = CustomTextEdit()
        self._notes_edit.setMaximumHeight(100)
        layout.addWidget(self._notes_edit)
        
        # Create buttons
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Save")
        self.add_button.clicked.connect(self.accept)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.add_button)
        layout.addLayout(button_layout)
        
        # Set tab order
        self.setTabOrder(self._source_text_edit, self._translated_text_edit)
        self.setTabOrder(self._translated_text_edit, self._notes_edit)
        self.setTabOrder(self._notes_edit, self.add_button)
        self.setTabOrder(self.add_button, self.cancel_button)
        self.setTabOrder(self.cancel_button, self._source_text_edit)  # Complete the cycle
        
        # If editing existing translation, populate fields
        if translation:
            self._source_text_edit.setPlainText(translation['source_text'])
            self._translated_text_edit.setPlainText(translation['translated_text'])
            self._notes_edit.setPlainText(translation.get('notes', ''))
    
    @property
    def source_text(self):
        return self._source_text_edit.toPlainText().strip()
    
    @property
    def translated_text(self):
        return self._translated_text_edit.toPlainText().strip()
    
    @property
    def notes(self):
        return self._notes_edit.toPlainText().strip()
    
    def validate_inputs(self):
        """Validate the input fields and show appropriate error messages"""
        if not self.source_text:
            QMessageBox.warning(
                self, 
                "Missing Source Text",
                "Please enter the source text. This field cannot be empty."
            )
            self._source_text_edit.setFocus()
            return False
            
        if not self.translated_text:
            QMessageBox.warning(
                self, 
                "Missing Translation",
                "Please enter the translated text. This field cannot be empty."
            )
            self._translated_text_edit.setFocus()
            return False
            
        return True
    
    def accept(self):
        if not self.validate_inputs():
            return
        super().accept() 