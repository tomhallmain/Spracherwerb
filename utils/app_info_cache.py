import datetime
import json
import os
import shutil
import threading

from lib.position_data import PositionData
from utils.globals import AppInfo
from utils.encryptor import encrypt_data_to_file, decrypt_data_from_file
from utils.runner_app_config import RunnerAppConfig
from utils.logging_setup import get_logger
from utils.translations import I18N

logger = get_logger(__name__)
_ = I18N._


class AppInfoCache:
    CACHE_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "app_info_cache.enc")
    JSON_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "app_info_cache.json")
    INFO_KEY = "info"
    NUM_BACKUPS = 4  # Number of backup files to maintain

    def __init__(self):
        self._lock = threading.RLock()
        self._cache = {AppInfoCache.INFO_KEY: {}}
        self.load()
        self.validate()

    def store(self):
        """Persist cache to encrypted file. Returns True on success, False if encrypted store failed but JSON fallback succeeded. Raises on encoding or JSON fallback failure."""
        with self._lock:
            try:
                cache_data = json.dumps(self._cache).encode('utf-8')
            except Exception as e:
                raise Exception(_("Error compiling application cache: {}").format(e))

            try:
                encrypt_data_to_file(
                    cache_data,
                    AppInfo.SERVICE_NAME,
                    AppInfo.APP_IDENTIFIER,
                    AppInfoCache.CACHE_LOC
                )
                return True  # Encryption successful
            except Exception as e:
                logger.error(_("Error encrypting cache: {}").format(e))

            try:
                with open(self.JSON_LOC, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f)
                return False  # Encryption failed, but JSON fallback succeeded
            except Exception as e:
                raise Exception(_("Error storing application cache: {}").format(e))

    def _try_load_cache_from_file(self, path):
        """Attempt to load and decrypt the cache from the given file path. Raises on failure."""
        encrypted_data = decrypt_data_from_file(
            path,
            AppInfo.SERVICE_NAME,
            AppInfo.APP_IDENTIFIER
        )
        return json.loads(encrypted_data.decode('utf-8'))

    def load(self):
        """Load the cache from encrypted file"""
        with self._lock:
            try:
                if os.path.exists(AppInfoCache.JSON_LOC):
                    logger.info(_("Detected JSON-format application cache, will attempt migration to encrypted store"))
                    # Get the old data first
                    with open(AppInfoCache.JSON_LOC, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                    if self.store():
                        logger.info(_("Migrated application cache from {} to encrypted store").format(self.JSON_LOC))
                        os.remove(self.JSON_LOC)
                    else:
                        logger.warning(_("Encrypted store of application cache failed; keeping JSON cache file"))
                    return

                # Try encrypted cache and backups in order
                cache_paths = [self.CACHE_LOC] + self._get_backup_paths()
                any_exist = any(os.path.exists(path) for path in cache_paths)
                if not any_exist:
                    logger.info(f"No cache file found at {self.CACHE_LOC}, creating new cache")
                    return

                for path in cache_paths:
                    if os.path.exists(path):
                        try:
                            self._cache = self._try_load_cache_from_file(path)
                            # Only shift backups if we loaded from the main file
                            if path == self.CACHE_LOC:
                                message = f"Loaded cache from {self.CACHE_LOC}"
                                rotated_count = self._rotate_backups()
                                if rotated_count > 0:
                                    message += f", rotated {rotated_count} backups"
                                logger.info(message)
                            else:
                                logger.warning(f"Loaded cache from backup: {path}")
                            return
                        except Exception as e:
                            logger.error(f"Failed to load cache from {path}: {e}")
                            continue
                # If we get here, all attempts failed (but at least one file existed)
                raise Exception(f"Failed to load cache from all locations: {cache_paths}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error(_("Error loading cache: {}").format(str(e)))
                # If decryption fails, start with empty cache
                self._cache = {AppInfoCache.INFO_KEY: {}}

    def validate(self):
        with self._lock:
            return True

    def set(self, key, value):
        with self._lock:
            if AppInfoCache.INFO_KEY not in self._cache:
                self._cache[AppInfoCache.INFO_KEY] = {}
            self._cache[AppInfoCache.INFO_KEY][key] = value

    def get(self, key, default_val=None):
        with self._lock:
            if AppInfoCache.INFO_KEY not in self._cache or key not in self._cache[AppInfoCache.INFO_KEY]:
                return default_val
            return self._cache[AppInfoCache.INFO_KEY][key]

    def set_display_position(self, master):
        """Store the main window's display position and size."""
        self.set("display_position", PositionData.from_master(master).to_dict())
    
    def set_virtual_screen_info(self, master):
        """Store the virtual screen information."""
        try:
            self.set("virtual_screen_info", PositionData.from_master_virtual_screen(master).to_dict())
        except Exception as e:
            logger.warning(f"Failed to store virtual screen info: {e}")
    
    def get_virtual_screen_info(self):
        """Get the cached virtual screen info, returns None if not set or invalid."""
        virtual_screen_data = self.get("virtual_screen_info")
        if not virtual_screen_data:
            return None
        return PositionData.from_dict(virtual_screen_data)

    def get_display_position(self):
        """Get the cached display position, returns None if not set or invalid."""
        position_data = self.get("display_position")
        if not position_data:
            return None
        return PositionData.from_dict(position_data)

    def _get_backup_paths(self):
        """Get list of backup file paths in order of preference"""
        backup_paths = []
        for i in range(1, self.NUM_BACKUPS + 1):
            index = "" if i == 1 else f"{i}"
            path = f"{self.CACHE_LOC}.bak{index}"
            backup_paths.append(path)
        return backup_paths

    def _rotate_backups(self):
        """Rotate backup files: move each backup to the next position, oldest gets overwritten"""
        backup_paths = self._get_backup_paths()
        rotated_count = 0
        
        # Remove the oldest backup if it exists
        if os.path.exists(backup_paths[-1]):
            os.remove(backup_paths[-1])
        
        # Shift backups: move each backup to the next position
        for i in range(len(backup_paths) - 1, 0, -1):
            if os.path.exists(backup_paths[i - 1]):
                shutil.copy2(backup_paths[i - 1], backup_paths[i])
                rotated_count += 1
        
        # Copy main cache to first backup position
        shutil.copy2(self.CACHE_LOC, backup_paths[0])
        
        return rotated_count

app_info_cache = AppInfoCache()
