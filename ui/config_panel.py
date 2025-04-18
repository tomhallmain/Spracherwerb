from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox, 
                             QGroupBox, QFormLayout, QPushButton,
                             QListWidget, QLabel)
from PySide6.QtCore import Qt

from ui.gutenberg_search_window import GutenbergSearchWindow


class ConfigPanel(QWidget):
    """Left sidebar for configuration options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)
        
        # Create layout
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # Language Settings Group
        language_group = QGroupBox("Language Settings")
        language_layout = QFormLayout()
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "German", "French", "Spanish", "Italian"])
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Beginner", "Intermediate", "Advanced"])
        
        language_layout.addRow("Target Language:", self.language_combo)
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
        
        # Add groups to main layout
        layout.addWidget(language_group)
        layout.addWidget(mode_group)
        layout.addWidget(books_group)
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
    
    def get_selected_books(self):
        """Get the list of selected Gutenberg books."""
        return self.selected_books 