"""Pluggable storage backend for database backups.

Only local disk storage is implemented today. The interface is deliberately
narrow (save / delete / open_for_download) so a cloud backend (Google Drive,
S3, Dropbox) can be added later as a second class implementing the same
three methods, without touching backup_engine.py or the views.
"""
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

BACKUP_ROOT = settings.BASE_DIR / "backups"


class StorageUnavailableError(Exception):
    """Raised when a configured storage backend isn't implemented yet."""


class LocalBackupStorage:
    location_code = "local"

    def __init__(self):
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    def save(self, file_name, content_bytes):
        """Writes content_bytes to BACKUP_ROOT/file_name. Returns the absolute path."""
        path = BACKUP_ROOT / file_name
        with open(path, "wb") as f:
            f.write(content_bytes)
        return str(path)

    def delete(self, file_path):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            # Don't let a stray locked/permission-denied file crash retention
            # cleanup or a delete request, but never fail silently -- an
            # orphaned file that outlives its BackupRecord should be visible
            # in server logs, not just vanish.
            logger.warning("Could not delete backup file: %s", file_path, exc_info=True)

    def open_for_download(self, file_path):
        """Returns a binary file object for streaming. Caller is responsible for closing it."""
        return open(file_path, "rb")


def get_storage_backend(storage_location="local"):
    if storage_location == "local":
        return LocalBackupStorage()
    raise StorageUnavailableError(
        f"'{storage_location}' storage is not available yet. Only Local Server storage is supported currently."
    )
