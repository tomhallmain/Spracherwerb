from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLineEdit, QLabel,
                             QComboBox, QHeaderView, QMessageBox, QMainWindow,
                             QSizePolicy)
from PySide6.QtCore import Qt, QDateTime, Signal, QSize
from PySide6.QtGui import QShortcut, QKeySequence
import json
import os
from datetime import datetime

from utils.config import config
from utils.translations import I18N
from utils.translation_data_manager import TranslationDataManager
from ui.translation_dialog import TranslationDialog

class TranslationsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Translation Notes")
        self.setMinimumSize(800, 600)
        
        # Initialize data manager
        self.data_manager = TranslationDataManager()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Initialize translations data
        self.translations = []
        self.load_translations()
        
        # Create main layout
        layout = QVBoxLayout(central_widget)
        
        # Create language display
        language_layout = QHBoxLayout()
        self.source_language_label = QLabel(f"Source: {I18N.get_language_name(config.source_language)}")
        self.target_language_label = QLabel(f"Target: {I18N.get_language_name(config.target_language)}")
        language_layout.addWidget(self.source_language_label)
        language_layout.addWidget(self.target_language_label)
        layout.addLayout(language_layout)
        
        # Create search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search translations...")
        self.search_input.textChanged.connect(self.filter_translations)
        search_layout.addWidget(self.search_input)
        
        # Create sort combo box
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Date Added (Newest)", "Date Added (Oldest)", 
                                "Source Text", "Translated Text"])
        self.sort_combo.currentIndexChanged.connect(self.sort_translations)
        search_layout.addWidget(self.sort_combo)
        
        # Add new translation button
        self.add_button = QPushButton("Add Translation")
        self.add_button.clicked.connect(self.add_translation)
        search_layout.addWidget(self.add_button)
        
        layout.addLayout(search_layout)
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(5)  # Removed date column
        self.table.setHorizontalHeaderLabels(["", "Source Text", "Translated Text", "Notes", ""])
        
        # Set column resize modes
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Edit button
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Source text
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Translated text
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Notes
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Remove button
        
        # Set row height
        self.table.verticalHeader().setDefaultSectionSize(24)  # Reduced from default
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        
        # Add keyboard shortcut for adding translations
        self.add_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.add_shortcut.activated.connect(self.add_translation)
        
        # Populate table with filtered translations
        self.update_table()
        
        # Set window flags to ensure it's a proper window
        self.setWindowFlags(Qt.Window)
    
    def load_translations(self):
        """Load translations from file"""
        try:
            # Load translations filtered for current language combination
            filtered_translations = self.data_manager.load_translations(
                source_language=config.source_language,
                target_language=config.target_language
            )
            
            # Convert date strings to datetime objects
            for t in filtered_translations:
                t['datetime'] = datetime.strptime(t['date_added'], '%Y-%m-%d %H:%M:%S')
            
            self.translations = filtered_translations
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load translations: {str(e)}")
            self.translations = []
    
    def save_translations(self):
        """Save translations to file"""
        try:
            # Convert current translations to save format
            save_translations = []
            for t in self.translations:
                save_t = t.copy()
                save_t['date_added'] = save_t['datetime'].strftime('%Y-%m-%d %H:%M:%S')
                del save_t['datetime']
                save_translations.append(save_t)
            
            # Try to save with data manager, providing current language combination
            if not self.data_manager.save_translations(
                save_translations,
                source_language=config.source_language,
                target_language=config.target_language
            ):
                # If save failed due to potential data loss, ask user
                reply = QMessageBox.question(
                    self, 
                    "Confirm Save",
                    "Saving these translations would result in significant data loss. Are you sure you want to continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # Try again with force=True
                    if not self.data_manager.save_translations(
                        save_translations,
                        source_language=config.source_language,
                        target_language=config.target_language,
                        force=True
                    ):
                        QMessageBox.warning(self, "Error", "Failed to save translations even with force option.")
                else:
                    QMessageBox.information(self, "Save Cancelled", "Translation save was cancelled to prevent data loss.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save translations: {str(e)}")
    
    def update_language_display(self):
        """Update the language display labels when languages change"""
        self.source_language_label.setText(f"Source: {I18N.get_language_name(config.source_language)}")
        self.target_language_label.setText(f"Target: {I18N.get_language_name(config.target_language)}")
        self.load_translations()  # Reload translations with new language filter
        self.update_table()
    
    def update_table(self):
        """Update the table with current translations"""
        self.table.setRowCount(len(self.translations))
        for i, trans in enumerate(self.translations):
            # Edit button
            edit_button = QPushButton("Edit")
            edit_button.setFixedSize(50, 20)  # Smaller button size
            edit_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            edit_button.setStyleSheet("QPushButton { padding: 0px; margin: 0px; }")
            edit_button.clicked.connect(lambda checked, idx=i: self.edit_translation(idx))
            self.table.setCellWidget(i, 0, edit_button)
            
            # Source text
            source_item = QTableWidgetItem(trans['source_text'])
            self.table.setItem(i, 1, source_item)
            
            # Translated text
            trans_item = QTableWidgetItem(trans['translated_text'])
            self.table.setItem(i, 2, trans_item)
            
            # Notes
            notes_item = QTableWidgetItem(trans.get('notes', ''))
            self.table.setItem(i, 3, notes_item)
            
            # Remove button
            remove_button = QPushButton("Remove")
            remove_button.setFixedSize(60, 20)  # Smaller button size
            remove_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            remove_button.setStyleSheet("QPushButton { padding: 0px; margin: 0px; }")
            remove_button.clicked.connect(lambda checked, idx=i: self.remove_translation(idx))
            self.table.setCellWidget(i, 4, remove_button)
    
    def filter_translations(self):
        """Filter translations based on search text"""
        search_text = self.search_input.text().lower()
        for i in range(self.table.rowCount()):
            match = False
            for j in range(1, 4):  # Skip edit and remove button columns
                item = self.table.item(i, j)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(i, not match)
    
    def sort_translations(self):
        """Sort translations based on selected criteria"""
        sort_index = self.sort_combo.currentIndex()
        if sort_index == 0:  # Date Added (Newest)
            self.translations.sort(key=lambda x: x['datetime'], reverse=True)
        elif sort_index == 1:  # Date Added (Oldest)
            self.translations.sort(key=lambda x: x['datetime'])
        elif sort_index == 2:  # Source Text
            self.translations.sort(key=lambda x: x['source_text'].lower())
        elif sort_index == 3:  # Translated Text
            self.translations.sort(key=lambda x: x['translated_text'].lower())
        self.update_table()
    
    def add_translation(self):
        """Add a new translation"""
        dialog = TranslationDialog(self)
        if dialog.exec_():
            new_t = {
                'datetime': datetime.now(),
                'source_text': dialog.source_text,
                'translated_text': dialog.translated_text,
                'notes': dialog.notes,
                'source_language': config.source_language,
                'target_language': config.target_language
            }
            self.translations.insert(0, new_t)
            self.save_translations()
            self.update_table()
    
    def edit_translation(self, index):
        """Edit an existing translation"""
        dialog = TranslationDialog(self, self.translations[index])
        if dialog.exec_():
            self.translations[index].update({
                'source_text': dialog.source_text,
                'translated_text': dialog.translated_text,
                'notes': dialog.notes
            })
            self.save_translations()
            self.update_table()
    
    def remove_translation(self, index):
        """Remove a translation"""
        translation = self.translations[index]
        source_text = translation['source_text']
        target_text = translation['translated_text']
        
        # Truncate texts if they're too long
        max_length = 50
        if len(source_text) > max_length:
            source_text = source_text[:max_length] + "..."
        if len(target_text) > max_length:
            target_text = target_text[:max_length] + "..."
        
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove this translation?\n\n"
            f"Source: {source_text}\n"
            f"Target: {target_text}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.translations[index]
            self.save_translations()
            self.update_table() 