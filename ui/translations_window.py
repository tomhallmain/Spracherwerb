from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLineEdit, QLabel,
                             QComboBox, QHeaderView, QMessageBox, QSizePolicy,
                             QFileDialog)
from PySide6.QtCore import Qt, QDateTime, Signal, QSize
from PySide6.QtGui import QShortcut, QKeySequence
import csv
import os
from datetime import datetime

from lib.multi_display import SmartWindow
from utils.config import config
from utils.globals import Language
from utils.translations import I18N
from utils.translation_data_manager import TranslationDataManager
from ui.translation_dialog import TranslationDialog

class TranslationsWindow(SmartWindow):
    def __init__(self, parent=None, **kwargs):
        super().__init__(persistent_parent=parent, title="Translation Notes", geometry="800x600", **kwargs)
        self.setMinimumSize(800, 600)
        
        # Initialize data manager
        self.data_manager = TranslationDataManager()
        
        # Initialize translations data
        self.translations = []
        self.load_translations()
        
        # Main layout on self (SmartWindow is QWidget, no setCentralWidget)
        layout = QVBoxLayout(self)
        
        # Create language display
        language_layout = QHBoxLayout()
        self.source_language_label = QLabel(f"Source: {Language.get_language_name(config.source_language)}")
        self.target_language_label = QLabel(f"Target: {Language.get_language_name(config.target_language)}")
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
        
        # Import translations button
        self.import_button = QPushButton("Import")
        self.import_button.setToolTip(
            "Import translations from a CSV or TSV file into the currently "
            "selected language pair. Each row must include source_text and "
            "translated_text. Other fields (notes, date_added) are optional."
        )
        self.import_button.clicked.connect(self.import_translations)
        search_layout.addWidget(self.import_button)

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
        """Load translations from file, backfilling any missing date_added stamps."""
        try:
            self.translations = self.data_manager.get_language_pair_with_dates(
                config.source_language,
                config.target_language,
                on_warning=lambda msg: QMessageBox.warning(self, "Warning", msg),
            )
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
                save_t['date_added'] = save_t['datetime'].strftime(TranslationDataManager.DATE_ADDED_FORMAT)
                del save_t['datetime']
                save_translations.append(save_t)
            
            # Save using new structured API for the current language pair
            if not self.data_manager.save_language_pair(
                save_translations,
                config.source_language,
                config.target_language
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
                    if not self.data_manager.save_language_pair(
                        save_translations,
                        config.source_language,
                        config.target_language,
                        force=True
                    ):
                        QMessageBox.warning(self, "Error", "Failed to save translations even with force option.")
                else:
                    QMessageBox.information(self, "Save Cancelled", "Translation save was cancelled to prevent data loss.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save translations: {str(e)}")
    
    def update_language_display(self):
        """Update the language display labels when languages change"""
        self.source_language_label.setText(f"Source: {Language.get_language_name(config.source_language)}")
        self.target_language_label.setText(f"Target: {Language.get_language_name(config.target_language)}")
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

    # ---- Import ---------------------------------------------------------

    # Map flexible header/key names to canonical translation fields. The
    # source/target language are intentionally not accepted from the imported
    # file: imports always use the language pair currently selected in the
    # window.
    _IMPORT_FIELD_ALIASES = {
        'source_text':      {'source_text', 'source_language', 'source', 'src', 'original', 'from_text', 'original_text', 'from'},
        'translated_text':  {'translated_text', 'target_language', 'translated', 'translation', 'target', 'tgt', 'to_text', 'target_text', 'to'},
        'notes':            {'notes', 'note', 'comment', 'comments', 'remark', 'remarks'},
        'date_added':       {'date_added', 'date', 'added', 'created', 'created_at', 'timestamp'},
    }

    def import_translations(self):
        """Import translations from a CSV or TSV file into the active language pair."""
        source_language = self._coerce_str(getattr(config, 'source_language', ''))
        target_language = self._coerce_str(getattr(config, 'target_language', ''))
        if not source_language or not target_language:
            QMessageBox.warning(
                self,
                "Import",
                "Please select a source and target language before importing."
            )
            return

        pair_label = (
            f"{Language.get_language_name(source_language)} "
            f"\u2192 {Language.get_language_name(target_language)}"
        )

        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Translations",
            "",
            "Translation files (*.csv *.tsv);;CSV (*.csv);;TSV (*.tsv);;All files (*)"
        )
        if not file_path:
            return

        try:
            raw_rows = self._parse_import_file(file_path)
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", f"Could not read the file:\n{str(e)}")
            return

        if not raw_rows:
            QMessageBox.information(self, "Import", "The file does not contain any translations.")
            return

        valid_rows, skipped = self._normalize_imported_rows(
            raw_rows, source_language, target_language
        )
        if not valid_rows:
            msg = "The file did not contain any usable translations."
            if skipped:
                msg += (
                    f"\n\n{self._pluralize(len(skipped), 'row was', 'rows were')} skipped "
                    "because the source or translated text was missing."
                )
            else:
                msg += "\n\nEach row needs a source text and a translated text."
            QMessageBox.warning(self, "Import", msg)
            return

        confirm_msg = (
            f"Import {self._pluralize(len(valid_rows), 'translation')} "
            f"as {pair_label}?"
        )
        if skipped:
            confirm_msg += (
                f"\n\n{self._pluralize(len(skipped), 'row will', 'rows will')} be skipped "
                "because the source or translated text is missing."
            )
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        try:
            existing = self.data_manager.get_language_pair(source_language, target_language) or []
        except Exception as e:
            QMessageBox.warning(
                self,
                "Import Failed",
                f"Could not load existing translations:\n{str(e)}"
            )
            return

        existing_keys = {
            TranslationsWindow._import_duplicate_key(
                e.get('source_text'), e.get('translated_text'))
            for e in existing
        }
        unique_new = []
        duplicate_count = 0
        for t in valid_rows:
            key = TranslationsWindow._import_duplicate_key(
                t['source_text'], t['translated_text'])
            if key in existing_keys:
                duplicate_count += 1
                continue
            existing_keys.add(key)
            unique_new.append(t)

        imported_count = 0
        save_failed = False
        if unique_new:
            combined = existing + unique_new
            if self.data_manager.save_language_pair(
                combined, source_language, target_language, force=True
            ):
                imported_count = len(unique_new)
            else:
                save_failed = True

        # Refresh the current view to surface the newly imported rows.
        self.load_translations()
        self.update_table()

        result_lines = [
            f"Imported {self._pluralize(imported_count, 'translation')} into {pair_label}."
        ]
        if duplicate_count:
            result_lines.append(
                f"Skipped {self._pluralize(duplicate_count, 'duplicate')} "
                "already in your translations."
            )
        if skipped:
            result_lines.append(
                f"Skipped {self._pluralize(len(skipped), 'row')} with missing "
                "source or translated text."
            )
        if save_failed:
            result_lines.append("The save did not complete; no changes were written.")
        QMessageBox.information(self, "Import Complete", "\n".join(result_lines))

    def _parse_import_file(self, file_path):
        """Parse a CSV/TSV import file into a list of row dicts.

        Raises:
            ValueError: if the file extension is unsupported
            OSError, csv.Error: on read/parse failure
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext not in ('.csv', '.tsv'):
            raise ValueError(f"Unsupported file extension: {ext}")

        delimiter = '\t' if ext == '.tsv' else ','
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            return [self._normalize_row_keys(row) for row in reader]

    @classmethod
    def _normalize_row_keys(cls, row):
        """Map flexible header/key names to canonical fields, preserving extras."""
        if not isinstance(row, dict):
            return {}
        normalized = {}
        for raw_key, value in row.items():
            if raw_key is None:
                continue
            key = str(raw_key).strip().lower().replace(' ', '_').replace('-', '_')
            mapped = None
            for canonical, group in cls._IMPORT_FIELD_ALIASES.items():
                if key in group:
                    mapped = canonical
                    break
            normalized[mapped or key] = value
        return normalized

    @staticmethod
    def _coerce_str(value):
        if value is None:
            return ''
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _pluralize(count, singular, plural=None):
        """Return e.g. '1 translation' or '617 translations'."""
        if plural is None:
            plural = singular + 's'
        return f"{count} {singular if count == 1 else plural}"

    @classmethod
    def _row_is_blank(cls, row):
        """True when a parsed row has no non-empty values (e.g. trailing empty CSV line)."""
        if not isinstance(row, dict):
            return True
        for value in row.values():
            if isinstance(value, list):
                # csv.DictReader puts extra trailing-comma fields in a list under None
                if any(cls._coerce_str(v) for v in value):
                    return False
            elif cls._coerce_str(value):
                return False
        return True

    @staticmethod
    def _import_duplicate_key(source_text, translated_text):
        """Trimmed, case-insensitive key for import deduplication only."""
        return (
            TranslationsWindow._coerce_str(source_text).casefold(),
            TranslationsWindow._coerce_str(translated_text).casefold(),
        )

    @staticmethod
    def _primary_language_tag(language_code):
        """BCP 47 primary language subtag (e.g. en-US → en), lowercased."""
        if not language_code:
            return ''
        return str(language_code).strip().lower().replace('_', '-').split('-')[0]

    # Languages where uppercasing only the first character still matches typical
    # imported phrase/sentence conventions. German (mandatory noun caps), Romance
    # languages (lighter capitalization than English in titles and headings),
    # Latin (often lowercase in sources), Turkic locales with dotted-I rules,
    # and unknown codes default to preserving file casing.
    _AUTO_CAPITALIZE_PRIMARY_TAGS = frozenset({
        'en',
        'nl', 'af',
        'sv', 'no', 'nb', 'nn', 'da', 'is', 'fo',
        'fi',
        'pl', 'cs', 'sk', 'hr', 'sl',
        'bg', 'sr', 'mk', 'ru', 'uk', 'be',
        'el',
        'et', 'lv', 'lt',
        'hu', 'ro',
        'sq',
        'ga', 'cy',
        'mt',
    })

    @classmethod
    def _capitalize_first(cls, text, language_code):
        """Uppercase the first character only when the language allowlists it."""
        if not text:
            return text
        primary = cls._primary_language_tag(language_code)
        if primary not in cls._AUTO_CAPITALIZE_PRIMARY_TAGS:
            return text
        return text[0].upper() + text[1:]

    def _normalize_imported_rows(self, rows, source_language, target_language):
        """Validate rows and stamp the active pair onto each one.

        Returns:
            tuple[list[dict], list]: (valid_rows, skipped_rows)
        """
        valid = []
        skipped = []

        for raw in rows:
            if not isinstance(raw, dict):
                skipped.append(raw)
                continue

            # Silently drop entirely-empty rows (e.g. trailing blank line in a CSV).
            if self._row_is_blank(raw):
                continue

            source_text = self._coerce_str(raw.get('source_text'))
            translated_text = self._coerce_str(raw.get('translated_text'))

            if not source_text or not translated_text:
                skipped.append(raw)
                continue

            source_text = self._capitalize_first(source_text, source_language)
            translated_text = self._capitalize_first(translated_text, target_language)

            date_added = self._coerce_str(raw.get('date_added'))
            if not date_added:
                date_added = datetime.now().strftime(TranslationDataManager.DATE_ADDED_FORMAT)

            valid.append({
                'source_text': source_text,
                'translated_text': translated_text,
                'source_language': source_language,
                'target_language': target_language,
                'notes': self._coerce_str(raw.get('notes')),
                'date_added': date_added,
            })

        return valid, skipped
