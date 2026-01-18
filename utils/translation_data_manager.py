import json
import shutil
from pathlib import Path
import appdirs
from collections import defaultdict

from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger("translation_data_manager")


class TranslationDataManager:
    """Manages translation data with structured storage by language pairs"""
    
    def __init__(self):
        # Use appdirs to get proper cache directory
        self.app_name = "Spracherwerb"
        self.app_author = "Spracherwerb"
        self.cache_dir = Path(appdirs.user_cache_dir(self.app_name, self.app_author))
        self.data_dir = self.cache_dir / "translations"
        self.data_file = self.data_dir / "translations_structured.json"
        self.backup_file = self.data_dir / "translations_structured_backup.json"
        self.user_backup_file = None
        
        logger.debug(f"Data file: {self.data_file}")
        logger.debug(f"Backup file: {self.backup_file}")
        
        if hasattr(config, 'backup_dir') and config.backup_dir and config.backup_dir.strip() != "":
            if Path(config.backup_dir).exists():
                self.user_backup_file = Path(config.backup_dir) / "translations_structured_backup.json"
                logger.debug(f"User backup file: {self.user_backup_file}")

        # Create necessary directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Migrate old format if it exists
        self._migrate_old_format()
    
    def _migrate_old_format(self):
        """Migrate from old flat list format to new structured format"""
        old_data_file = self.data_dir / "translations.json"
        
        if not old_data_file.exists():
            return  # No migration needed
        
        if self.data_file.exists():
            # Already migrated, but check if old file is newer
            old_mtime = old_data_file.stat().st_mtime
            new_mtime = self.data_file.stat().st_mtime
            
            if old_mtime > new_mtime:
                logger.warning("Old translations file is newer than structured file. Re-migrating.")
            else:
                return  # Already migrated and up-to-date
        
        try:
            logger.info("Migrating from old flat format to structured format...")
            
            # Load old format
            with open(old_data_file, 'r', encoding='utf-8') as f:
                old_translations = json.load(f)
            
            if not old_translations:
                logger.info("No translations to migrate")
                return
            
            # Convert to structured format
            structured_data = {}
            for trans in old_translations:
                source = trans.get('source_language')
                target = trans.get('target_language')
                
                if not source or not target:
                    logger.warning(f"Skipping translation without language info: {trans.get('source_text', 'Unknown')}")
                    continue
                
                pair_key = f"{source}-{target}"
                if pair_key not in structured_data:
                    structured_data[pair_key] = []
                
                structured_data[pair_key].append(trans)
            
            # Save new format
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)
            
            # Backup old file
            old_backup = old_data_file.with_suffix('.json.old')
            shutil.copy2(old_data_file, old_backup)
            logger.info(f"Old format backed up to {old_backup}")
            
            logger.info(f"Migrated {len(old_translations)} translations to structured format")
            
        except Exception as e:
            logger.error(f"Error migrating old format: {e}")
    
    def get_language_pair(self, source_language, target_language):
        """Get all translations for a specific language pair"""
        try:
            if not self.data_file.exists():
                return []
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                structured_data = json.load(f)
            
            pair_key = f"{source_language}-{target_language}"
            return structured_data.get(pair_key, [])
            
        except Exception as e:
            logger.error(f"Error loading language pair {source_language}-{target_language}: {e}")
            return self._load_from_backup_pair(source_language, target_language)
    
    def save_language_pair(self, translations, source_language, target_language, force=False):
        """Save translations for a specific language pair"""
        try:
            if not source_language or not target_language:
                logger.error("Source and target language must be specified")
                return False
            
            # Create backup before saving
            self._create_backup()
            
            # Load existing structured data
            existing_data = self._load_structured_data()
            
            pair_key = f"{source_language}-{target_language}"
            
            # Check if we're about to lose significant data
            existing_for_pair = existing_data.get(pair_key, [])
            if not force and existing_for_pair and self._would_lose_data_for_pair(existing_for_pair, translations):
                logger.warning(f"Would lose data for {pair_key}. Use force=True to override.")
                return False
            
            # Update the pair
            existing_data[pair_key] = translations
            
            # Save
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(translations)} translations for {pair_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving language pair {source_language}-{target_language}: {e}")
            return False
    
    def add_translation(self, translation):
        """Add a single translation to the appropriate language pair"""
        try:
            source = translation.get('source_language')
            target = translation.get('target_language')
            
            if not source or not target:
                logger.error("Translation must have source_language and target_language")
                return False
            
            # Create backup
            self._create_backup()
            
            # Load existing structured data
            existing_data = self._load_structured_data()
            
            pair_key = f"{source}-{target}"
            
            # Initialize if not exists
            if pair_key not in existing_data:
                existing_data[pair_key] = []
            
            # Add translation
            existing_data[pair_key].append(translation)
            
            # Save
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Added translation to {pair_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding translation: {e}")
            return False
    
    def get_all_language_pairs(self):
        """Get all language pairs in the database"""
        try:
            if not self.data_file.exists():
                return {}
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                structured_data = json.load(f)
            
            # Return as sorted list of pairs
            return sorted(structured_data.keys())
            
        except Exception as e:
            logger.error(f"Error getting language pairs: {e}")
            return []
    
    def get_translation_stats(self):
        """Get statistics about translations"""
        try:
            if not self.data_file.exists():
                return {"total": 0, "by_pair": {}}
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                structured_data = json.load(f)
            
            stats = {"total": 0, "by_pair": {}}
            
            for pair_key, translations in structured_data.items():
                count = len(translations)
                stats["by_pair"][pair_key] = count
                stats["total"] += count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting translation stats: {e}")
            return {"total": 0, "by_pair": {}}
    
    def delete_language_pair(self, source_language, target_language):
        """Delete an entire language pair"""
        try:
            # Create backup
            self._create_backup()
            
            # Load existing structured data
            existing_data = self._load_structured_data()
            
            pair_key = f"{source_language}-{target_language}"
            
            if pair_key in existing_data:
                deleted_count = len(existing_data[pair_key])
                del existing_data[pair_key]
                
                # Save
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Deleted {deleted_count} translations for {pair_key}")
                return True
            else:
                logger.warning(f"Language pair {pair_key} not found")
                return False
            
        except Exception as e:
            logger.error(f"Error deleting language pair {source_language}-{target_language}: {e}")
            return False
    
    def _load_structured_data(self):
        """Load structured data, creating empty dict if file doesn't exist"""
        try:
            if not self.data_file.exists():
                return {}
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading structured data: {e}")
            return {}
    
    def _create_backup(self):
        """Create a backup of the current structured data file"""
        if not self.data_file.exists():
            return
        
        try:
            # Create automatic backup in cache directory
            shutil.copy2(self.data_file, self.backup_file)
            
            # Create backup in user-specified location if configured
            if self.user_backup_file and self.user_backup_file.parent.exists():
                self.user_backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.data_file, self.user_backup_file)
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
    
    def _load_from_backup_pair(self, source_language, target_language):
        """Load a specific language pair from backup"""
        try:
            backup_data = None
            
            # Try user-specified backup first
            if self.user_backup_file and self.user_backup_file.exists():
                with open(self.user_backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            
            # Fall back to automatic backup
            elif self.backup_file.exists():
                with open(self.backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            
            if backup_data:
                pair_key = f"{source_language}-{target_language}"
                return backup_data.get(pair_key, [])
            
            return []
            
        except Exception as e:
            logger.error(f"Error loading from backup for {source_language}-{target_language}: {e}")
            return []
    
    def _would_lose_data_for_pair(self, existing_for_pair, new_translations):
        """Check if saving new translations for a specific language pair would result in significant data loss"""
        try:
            # If there are fewer than 10 translations for this pair, don't check for data loss
            if len(existing_for_pair) < 10:
                return False

            # Consider it significant data loss if we're losing more than 10% of entries for this pair
            current_count = len(existing_for_pair)
            new_count = len(new_translations)
            
            return new_count < current_count * 0.9
            
        except Exception:
            return False


# Helper function for backward compatibility during transition
def get_legacy_compatible_manager():
    """Get a manager that can work with both old and new formats during transition"""
    manager = TranslationDataManager()
    
    # Create a wrapper that provides the old interface if needed
    class LegacyCompatibleManager:
        def __init__(self, new_manager):
            self.manager = new_manager
        
        def load_translations(self, source_language=None, target_language=None):
            """Compatibility wrapper for old load_translations method"""
            if source_language is None and target_language is None:
                # Return all translations flattened (for compatibility)
                stats = self.manager.get_translation_stats()
                all_translations = []
                
                pairs = self.manager.get_all_language_pairs()
                for pair in pairs:
                    source, target = pair.split('-')
                    translations = self.manager.get_language_pair(source, target)
                    all_translations.extend(translations)
                
                return all_translations
            elif source_language is not None and target_language is not None:
                # Get specific language pair
                return self.manager.get_language_pair(source_language, target_language)
            else:
                # Filter by source or target only (less efficient but for compatibility)
                all_translations = []
                pairs = self.manager.get_all_language_pairs()
                
                for pair in pairs:
                    source, target = pair.split('-')
                    
                    if (source_language is None or source == source_language) and \
                       (target_language is None or target == target_language):
                        translations = self.manager.get_language_pair(source, target)
                        all_translations.extend(translations)
                
                return all_translations
        
        def save_translations(self, translations, source_language=None, target_language=None, force=False):
            """Compatibility wrapper for old save_translations method"""
            if source_language is not None and target_language is not None:
                # Save specific language pair
                return self.manager.save_language_pair(translations, source_language, target_language, force)
            else:
                # This is the dangerous case - saving all translations
                # We'll need to restructure the data
                logger.warning("Using legacy save_translations without language pair - converting to structured format")
                
                # Group translations by language pair
                structured_data = {}
                for trans in translations:
                    source = trans.get('source_language')
                    target = trans.get('target_language')
                    
                    if source and target:
                        pair_key = f"{source}-{target}"
                        if pair_key not in structured_data:
                            structured_data[pair_key] = []
                        structured_data[pair_key].append(trans)
                
                # Save each pair individually
                for pair_key, pair_translations in structured_data.items():
                    source, target = pair_key.split('-')
                    if not self.manager.save_language_pair(pair_translations, source, target, force):
                        return False
                
                return True
    
    return LegacyCompatibleManager(manager)