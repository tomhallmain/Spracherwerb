from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox, 
                             QGroupBox, QFormLayout, QPushButton,
                             QListWidget, QLabel)
from PySide6.QtCore import Qt, Signal

from ui.gutenberg_search_window import GutenbergSearchWindow
from utils.config import config
from utils.translations import I18N
from utils.globals import Language


class ConfigPanel(QWidget):
    """Left sidebar for configuration options"""
    # Signal emitted when languages change
    languages_changed = Signal()
    
    def __init__(self, parent=None, app_actions=None):
        super().__init__(parent)
        self.setMinimumWidth(250)
        self.app_actions = app_actions
        
        # Create layout
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # Language Settings Group
        language_group = QGroupBox("Language Settings")
        language_layout = QFormLayout()
        
        # Source language
        self.source_language_combo = QComboBox()
        # Use Language enum, but exclude Latin from source languages (typically not used as source)
        source_languages = [lang for lang in Language if lang != Language.LATIN]
        for lang in source_languages:
            self.source_language_combo.addItem(Language.get_language_name(lang.value), lang.value)
        self.source_language_combo.setCurrentText(Language.get_language_name(config.source_language))
        self.source_language_combo.currentTextChanged.connect(self.on_source_language_changed)
        
        # Target language (language being learned)
        self.target_language_combo = QComboBox()
        # Use Language enum for all supported languages
        for lang in Language:
            self.target_language_combo.addItem(Language.get_language_name(lang.value), lang.value)
        self.target_language_combo.setCurrentText(Language.get_language_name(config.target_language))
        self.target_language_combo.currentTextChanged.connect(self.on_target_language_changed)
        
        # Proficiency level
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Beginner", "Intermediate", "Advanced"])
        self.level_combo.setCurrentText(config.proficiency_level.capitalize())
        self.level_combo.currentTextChanged.connect(self.on_proficiency_level_changed)
        
        language_layout.addRow("Source Language:", self.source_language_combo)
        language_layout.addRow("Target Language:", self.target_language_combo)
        language_layout.addRow("Proficiency Level:", self.level_combo)
        language_group.setLayout(language_layout)
        
        # Learning Mode Group
        mode_group = QGroupBox("Learning Mode")
        mode_layout = QFormLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Vocabulary Building",
            "Grammar Practice",
            "Conversation",
            "Writing Practice",
            "Cultural Learning"
        ])
        
        mode_layout.addRow("Current Mode:", self.mode_combo)
        mode_group.setLayout(mode_layout)
        
        # Gutenberg Books Group
        books_group = QGroupBox("Learning Materials")
        books_layout = QVBoxLayout()
        
        # Button to open Gutenberg search
        self.search_button = QPushButton("Select Books from Gutenberg")
        self.search_button.clicked.connect(self._open_gutenberg_search)
        books_layout.addWidget(self.search_button)
        
        # Label for selected books
        self.books_label = QLabel("Selected Books:")
        books_layout.addWidget(self.books_label)
        
        # List widget for selected books
        self.books_list = QListWidget()
        self.books_list.setSelectionMode(QListWidget.NoSelection)  # Read-only
        books_layout.addWidget(self.books_list)
        
        books_group.setLayout(books_layout)
        
        # Translations Group
        translations_group = QGroupBox("Translations")
        translations_layout = QVBoxLayout()
        
        self.translations_button = QPushButton("Open Translation Notes")
        self.translations_button.clicked.connect(self._open_translations)
        translations_layout.addWidget(self.translations_button)
        
        translations_group.setLayout(translations_layout)
        
        # Add groups to main layout
        layout.addWidget(language_group)
        layout.addWidget(mode_group)
        layout.addWidget(books_group)
        layout.addWidget(translations_group)
        layout.addStretch()
        
        # Store selected books
        self.selected_books = []
    
    def _open_gutenberg_search(self):
        """Open the Gutenberg search window and handle book selection."""
        search_window = GutenbergSearchWindow(self)
        search_window.books_selected.connect(self._handle_selected_books)
        search_window.show()
    
    def _handle_selected_books(self, books):
        """Handle the selection of books from the Gutenberg search window."""
        self.selected_books = books
        self._update_books_list()
    
    def _update_books_list(self):
        """Update the list widget with the currently selected books."""
        self.books_list.clear()
        for book in self.selected_books:
            item_text = f"{book.title} - {', '.join(book.authors)}"
            if book.word_count:
                item_text += f" ({book.word_count} words)"
            self.books_list.addItem(item_text)
    
    def _open_translations(self):
        """Open the translations window using the app actions callback."""
        if self.app_actions and self.app_actions.open_translations:
            self.app_actions.open_translations()
    
    def on_source_language_changed(self, language):
        """Handle source language change."""
        config.source_language = Language.get_language_code(language)
        self.languages_changed.emit()
    
    def on_target_language_changed(self, language):
        """Handle target language change."""
        config.target_language = Language.get_language_code(language)
        self.languages_changed.emit()
    
    def on_proficiency_level_changed(self, level):
        """Handle proficiency level change."""
        config.proficiency_level = level.lower()
    
    def get_selected_books(self):
        """Get the list of selected Gutenberg books."""
        return self.selected_books 