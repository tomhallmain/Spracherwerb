
from extensions.extension_manager import ExtensionManager
from Spracherwerb.muse_memory import MuseMemory
from Spracherwerb.playlist import Playlist
from Spracherwerb.schedules_manager import SchedulesManager


class PersistentDataManager:
    @staticmethod
    def store():
        MuseMemory.save()
        Playlist.store_recently_played_lists()
        SchedulesManager.store_schedules()
        ExtensionManager.store_extensions()

    @staticmethod
    def load():
        MuseMemory.load()
        Playlist.load_recently_played_lists()
        SchedulesManager.set_schedules()
        ExtensionManager.load_extensions()

