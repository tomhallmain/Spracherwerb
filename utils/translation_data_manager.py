import json
import shutil
from pathlib import Path
import appdirs

from utils.config import config
from utils.utils import Utils

class TranslationDataManager:
    """Manages translation data storage and backup"""
    
    def __init__(self):
        # Use appdirs to get proper cache directory
        self.app_name = "Spracherwerb"
        self.app_author = "Spracherwerb"
        self.cache_dir = Path(appdirs.user_cache_dir(self.app_name, self.app_author))
        self.data_dir = self.cache_dir / "translations"
        self.data_file = self.data_dir / "translations.json"
        self.backup_file = self.data_dir / "translations_backup.json"
        Utils.log_debug(f"Data file: {self.data_file}")
        Utils.log_debug(f"Backup file: {self.backup_file}")
        if hasattr(config, 'backup_dir') and config.backup_dir and config.backup_dir.strip() != "":
            if Path(config.backup_dir).exists():
                backup_path = Path(config.backup_dir) / "translations_backup.json"
                Utils.log_debug(f"Backup file 2: {backup_path}")

        # Create necessary directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_translations(self, source_language=None, target_language=None):
        """Load translations from the data file with optional language filtering
        
        Args:
            source_language: If provided, filter by source language
            target_language: If provided, filter by target language
        """
        try:
            if not self.data_file.exists():
                return []
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
                
            # Apply language filters if provided
            if source_language is not None or target_language is not None:
                translations = [
                    t for t in translations
                    if (source_language is None or t['source_language'] == source_language) and
                       (target_language is None or t['target_language'] == target_language)
                ]
                
            return translations
        except Exception as e:
            Utils.log_red(f"Error loading translations: {e}")
            # Try to load from most recent backup
            return self._load_from_backup()
    
    def save_translations(self, translations, source_language=None, target_language=None, force=False):
        """Save translations with backup and safety checks
        
        Args:
            translations: List of translations to save
            source_language: If provided, these translations are for a specific source language
            target_language: If provided, these translations are for a specific target language
            force: If True, skip data loss checks
        """
        try:
            # Create backup before saving
            self._create_backup()
            
            # Load existing translations
            existing_translations = self.load_translations()
            
            # If language filters are provided, merge with existing translations
            if source_language is not None and target_language is not None:
                # Remove existing translations for this language combination
                existing_translations = [
                    t for t in existing_translations
                    if not (t['source_language'] == source_language and 
                           t['target_language'] == target_language)
                ]
                # Add new translations
                existing_translations.extend(translations)
                translations = existing_translations
            
            # Check if we're about to lose significant data
            if not force and self._would_lose_data(translations):
                return False
            
            # Save new data
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            Utils.log_red(f"Error saving translations: {e}")
            return False
    
    def _create_backup(self):
        """Create a backup of the current translations file"""
        if not self.data_file.exists():
            return
        
        try:
            # Create automatic backup in cache directory
            shutil.copy2(self.data_file, self.backup_file)
            
            # Create backup in user-specified location if configured
            if hasattr(config, 'backup_dir') and config.backup_dir and config.backup_dir.strip() != "":
                if Path(config.backup_dir).exists():
                    backup_path = Path(config.backup_dir) / "translations_backup.json"
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.data_file, backup_path)
                else:
                    Utils.log_red(f"Backup path provided {config.backup_dir} does not exist")
        except Exception as e:
            Utils.log_red(f"Error creating backup: {e}")
    
    def _load_from_backup(self):
        """Load translations from the most recent backup"""
        try:
            # Try user-specified backup first
            if hasattr(config, 'backup_dir') and config.backup_dir and config.backup_dir.strip() != "":
                if Path(config.backup_dir).exists():
                    backup_path = Path(config.backup_dir) / "translations_backup.json"
                    if backup_path.exists():
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    else:
                        Utils.log_red(f"Failed to load backup from {backup_path}")
                else:
                    Utils.log_red(f"Backup path provided {config.backup_dir} does not exist")
            
            # Fall back to automatic backup
            if self.backup_file.exists():
                with open(self.backup_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                Utils.log_red(f"Failed to load backup from {self.backup_file}")

            return []
        except Exception as e:
            Utils.log_red(f"Error loading from backup: {e}")
            return []
    
    def _would_lose_data(self, new_translations):
        """Check if saving new translations would result in significant data loss"""
        try:
            if not self.data_file.exists():
                return False
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                current_translations = json.load(f)

            if len(current_translations) < 10:
                return False

            # Consider it significant data loss if we're losing more than 10% of entries
            current_count = len(current_translations)
            new_count = len(new_translations)
            
            return new_count < current_count * 0.9
        except Exception:
            return False 