from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QComboBox, QListWidget, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot

from ui.base_window import BaseWindow
from extensions.gutenberg import Gutenberg, GutenbergBook
from utils.config import config


class GutenbergSearchWindow(BaseWindow):
    """Window for searching and selecting books from Project Gutenberg."""
    
    # Signal emitted when books are selected
    books_selected = Signal(list)  # List of GutenbergBook objects
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gutenberg Book Search")
        self.gutenberg = Gutenberg()
        self.selected_books = []
        
        # Initialize UI
        self._init_search_controls()
        self._init_results_list()
        self._init_selection_list()
        self._init_buttons()
        
        # Connect signals
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect all signals to their respective slots."""
        # Connect search input
        self.search_input.returnPressed.connect(self._perform_search)
        
        # Connect list widget interactions
        self.results_list.itemDoubleClicked.connect(self._add_selected_book)
        self.selection_list.itemDoubleClicked.connect(self._remove_selected_book)
        
        # Connect buttons
        self.search_button.clicked.connect(self._perform_search)
        self.add_button.clicked.connect(self._add_selected_book)
        self.remove_button.clicked.connect(self._remove_selected_book)
        self.save_button.clicked.connect(self._save_selection)
    
    def _init_search_controls(self):
        """Initialize the search controls section."""
        # Search input
        self.search_input = self.add_entry(
            placeholder="Enter search terms...",
            column=0
        )
        
        # Language selection
        self.language_combo = self.add_combo_box(
            items=self.gutenberg.get_available_languages(),
            column=0
        )
        
        # Search button
        self.search_button = self.add_button(
            "Search",
            self._perform_search,
            column=0
        )
    
    def _init_results_list(self):
        """Initialize the search results list."""
        self.results_label = self.add_label(
            "Search Results",
            column=1
        )
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.apply_to_grid(self.results_list, column=1)
    
    def _init_selection_list(self):
        """Initialize the selected books list."""
        self.selection_label = self.add_label(
            "Selected Books",
            column=1
        )
        self.selection_list = QListWidget()
        self.selection_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.apply_to_grid(self.selection_list, column=1)
    
    def _init_buttons(self):
        """Initialize the action buttons."""
        # Add selected button
        self.add_button = self.add_button(
            "Add Selected",
            self._add_selected_book,
            column=1
        )
        
        # Remove selected button
        self.remove_button = self.add_button(
            "Remove Selected",
            self._remove_selected_book,
            column=1
        )
        
        # Save selection button
        self.save_button = self.add_button(
            "Save Selection",
            self._save_selection,
            column=1
        )
    
    @Slot()
    def _perform_search(self):
        """Perform a search based on the current input."""
        search_term = self.search_input.text()
        language = self.language_combo.currentText()
        
        if not search_term:
            QMessageBox.warning(
                self,
                "Search Error",
                "Please enter a search term."
            )
            return
        
        # Clear previous results
        self.results_list.clear()
        
        # Perform search
        results = self.gutenberg.search_books(
            language=language,
            search_term=search_term
        )
        
        # Display results
        for book in results:
            item_text = f"{book.title} - {', '.join(book.authors)}"
            if book.word_count:
                item_text += f" ({book.word_count} words)"
            self.results_list.addItem(item_text)
            self.results_list.item(self.results_list.count() - 1).setData(
                Qt.UserRole, book
            )
    
    @Slot()
    def _add_selected_book(self):
        """Add the selected book(s) to the selection list."""
        selected_items = self.results_list.selectedItems()
        for item in selected_items:
            book = item.data(Qt.UserRole)
            if book not in self.selected_books:
                self.selected_books.append(book)
                item_text = f"{book.title} - {', '.join(book.authors)}"
                if book.word_count:
                    item_text += f" ({book.word_count} words)"
                self.selection_list.addItem(item_text)
                self.selection_list.item(self.selection_list.count() - 1).setData(
                    Qt.UserRole, book
                )
    
    @Slot()
    def _remove_selected_book(self):
        """Remove the selected book(s) from the selection list."""
        selected_items = self.selection_list.selectedItems()
        for item in selected_items:
            book = item.data(Qt.UserRole)
            if book in self.selected_books:
                self.selected_books.remove(book)
                self.selection_list.takeItem(self.selection_list.row(item))
    
    @Slot()
    def _save_selection(self):
        """Save the selected books and close the window."""
        if not self.selected_books:
            QMessageBox.warning(
                self,
                "Save Error",
                "Please select at least one book."
            )
            return
        
        # Emit the selected books signal
        self.books_selected.emit(self.selected_books)
        
        # Close the window
        self.close()
    
    def get_selected_books(self):
        """Get the list of selected books."""
        return self.selected_books 