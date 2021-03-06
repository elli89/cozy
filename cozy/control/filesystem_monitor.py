from pathlib import Path
import logging
from gi.repository import Gio

from cozy.architecture.event_sender import EventSender
from cozy.architecture.singleton import Singleton
import cozy.ui.settings
import cozy.ui
import cozy.tools as tools
from cozy.control.db import get_external_storage_locations, get_tracks
from cozy.model.book import Book

log = logging.getLogger("fs_monitor")

class FilesystemMonitor(EventSender, metaclass=Singleton):
    external_storage = []
    """
    This class handles all filesystem monitoring operations.
    """
    def __init__(self):
        self.volume_monitor = Gio.VolumeMonitor.get()
        self.volume_monitor.connect("mount-added", self.__on_mount_added)
        self.volume_monitor.connect("mount-removed", self.__on_mount_removed)

        self.init_offline_mode()

        cozy.ui.settings.Settings().add_listener(self.__on_settings_changed)

    def init_offline_mode(self):
        external_storage = []
        mounts = self.volume_monitor.get_mounts()
        # go through all audiobook locations and test if they can be found in the mounts list

        # Assume home is always online
        self.external_storage.append([str(Path.home()), True])

        for dir in get_external_storage_locations():
            online = False
            if any(mount.get_root().get_path() in dir.path for mount in mounts):
                online = True
            self.external_storage.append([dir.path, online])

    def close(self):
        """
        Free all references.
        """
        #self.volume_monitor.unref()
        pass

    def get_book_online(self, book: Book):
        result = next((storage[1] for storage in self.external_storage if storage[0] in book.chapters[0].file),
                      True)
        return result

    def is_book_online(self, book):
        """
        """
        result = next((storage[1] for storage in self.external_storage if storage[0] in get_tracks(book).first().file), True)
        return (result)

    def is_track_online(self, track):
        """
        """
        result = next((storage[1] for storage in self.external_storage if storage[0] in track.file), True)
        return (result)
    
    def get_offline_storages(self):
        return [i[0] for i in self.external_storage if not i[1]]

    def __on_mount_added(self, monitor, mount):
        """
        A volume was mounted.
        Disable offline mode for this volume.
        """
        mount_path = mount.get_root().get_path()
        log.debug("Volume mounted: " + mount_path)

        storage = next((s for s in self.external_storage if mount_path in s[0]), None)
        if storage:
            log.info("Storage online: " + mount_path)
            storage[1] = True
            self.emit_event("storage-online", storage[0])

    def __on_mount_removed(self, monitor, mount):
        """
        A volume was unmounted.
        Enable offline mode for this volume.
        """
        mount_path = mount.get_root().get_path()
        log.debug("Volume unmounted: " + mount_path)
        
        storage = next((s for s in self.external_storage if mount_path in s[0]), None)
        if storage:
            log.info("Storage offline: " + mount_path)
            storage[1] = False
            self.emit_event("storage-offline", storage[0])

            # switch to offline version if currently playing
        
    def __on_settings_changed(self, event, message):
        """
        This method reacts to storage settings changes.
        """
        if event == "external-storage-added" or event == "storage-changed" or (event == "storage-added" and message != ""):
            self.init_offline_mode()
        elif event == "storage-removed" or event == "external-storage-removed":
            self.external_storage = [item for item in self.external_storage if item[0] not in message]