"""Database backup/restore engine.

Handles both database engines this app actually runs on: SQLite (local dev,
via sqlite3's iterdump — a clean logical dump, not a raw file copy) and
PostgreSQL (production, via the pg_dump/psql CLI tools). Storage is delegated
to backup_storage.get_storage_backend() so a cloud backend can be swapped in
later without touching this module.
"""
import calendar
import gzip
import os
import sqlite3
import subprocess
from datetime import timedelta

from django.conf import settings
from django.db import connections
from django.utils import timezone

from .backup_storage import get_storage_backend


class BackupError(Exception):
    """Raised for any backup/restore failure with a user-facing message."""


def get_db_engine():
    engine = settings.DATABASES["default"]["ENGINE"]
    if "postgresql" in engine:
        return "postgresql"
    if "sqlite3" in engine:
        return "sqlite"
    return "unknown"


def compute_next_scheduled(settings_row, now=None):
    """Best-effort 'next scheduled backup' time for display purposes.

    Lives here (not in backup_views.py) so it has no dependency on views.py —
    both backup_views.py and views.py's dashboard() import it from here
    without risking a circular import (backup_views.py imports is_owner from
    views.py).
    """
    if not settings_row.auto_backup_enabled:
        return None
    now = now or timezone.localtime()
    today_target = now.replace(
        hour=settings_row.backup_time.hour, minute=settings_row.backup_time.minute,
        second=0, microsecond=0,
    )

    if settings_row.frequency == "daily":
        candidate = today_target
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if settings_row.frequency == "weekly":
        days_ahead = (settings_row.weekly_day - now.weekday()) % 7
        candidate = today_target + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    if settings_row.frequency == "monthly":
        year, month = now.year, now.month
        last_day = calendar.monthrange(year, month)[1]
        target_day = min(settings_row.monthly_day, last_day)
        candidate = today_target.replace(day=target_day)
        if candidate <= now:
            month += 1
            if month > 12:
                month = 1
                year += 1
            last_day = calendar.monthrange(year, month)[1]
            target_day = min(settings_row.monthly_day, last_day)
            candidate = candidate.replace(year=year, month=month, day=target_day)
        return candidate

    return None


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------
def _dump_sqlite():
    db_path = str(settings.DATABASES["default"]["NAME"])
    conn = sqlite3.connect(db_path)
    try:
        sql_text = "\n".join(conn.iterdump())
    finally:
        conn.close()
    return sql_text.encode("utf-8")


def _restore_sqlite(sql_bytes):
    db_path = str(settings.DATABASES["default"]["NAME"])
    tmp_path = db_path + ".restore_tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(sql_bytes.decode("utf-8"))
        conn.commit()
    except Exception as exc:
        conn.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise BackupError(f"Failed to apply SQLite restore script: {exc}") from exc
    else:
        conn.close()

    # Close Django's held connection(s) before swapping the file out from under it.
    connections.close_all()
    os.replace(tmp_path, db_path)


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
def _pg_connection_args(db_config):
    args = []
    if db_config.get("HOST"):
        args += ["-h", db_config["HOST"]]
    if db_config.get("PORT"):
        args += ["-p", str(db_config["PORT"])]
    if db_config.get("USER"):
        args += ["-U", db_config["USER"]]
    return args


def _pg_env(db_config):
    env = os.environ.copy()
    if db_config.get("PASSWORD"):
        env["PGPASSWORD"] = db_config["PASSWORD"]
    return env


def _dump_postgres(db_config):
    cmd = ["pg_dump", "--no-owner", "--format=plain"] + _pg_connection_args(db_config) + ["-d", db_config["NAME"]]
    try:
        result = subprocess.run(cmd, env=_pg_env(db_config), capture_output=True, timeout=1800)
    except FileNotFoundError as exc:
        raise BackupError(
            "pg_dump was not found on this server. Install the PostgreSQL client tools "
            "(the 'postgresql-client' package) or contact your hosting provider."
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise BackupError(f"pg_dump failed (exit {result.returncode}): {stderr[:2000]}")
    return result.stdout


def _restore_postgres(db_config, sql_bytes):
    cmd = (
        ["psql", "--no-psqlrc", "-v", "ON_ERROR_STOP=1"]
        + _pg_connection_args(db_config)
        + ["-d", db_config["NAME"]]
    )
    try:
        result = subprocess.run(cmd, input=sql_bytes, env=_pg_env(db_config), capture_output=True, timeout=1800)
    except FileNotFoundError as exc:
        raise BackupError(
            "psql was not found on this server. Install the PostgreSQL client tools "
            "(the 'postgresql-client' package) or contact your hosting provider."
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise BackupError(f"psql restore failed (exit {result.returncode}): {stderr[:2000]}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_backup(initiated_by=None, backup_type="manual"):
    from .models import BackupRecord, BackupSettings

    record = BackupRecord.objects.create(
        backup_type=backup_type,
        status="in_progress",
        initiated_by=initiated_by,
        db_engine=get_db_engine(),
    )
    try:
        engine = get_db_engine()
        if engine == "sqlite":
            raw_bytes = _dump_sqlite()
        elif engine == "postgresql":
            raw_bytes = _dump_postgres(settings.DATABASES["default"])
        else:
            raise BackupError(f"Unsupported database engine: {settings.DATABASES['default']['ENGINE']}")

        compressed = gzip.compress(raw_bytes)

        # Microsecond precision avoids filename collisions between backups
        # created within the same second (e.g. rapid consecutive manual runs).
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S_%f")
        file_name = f"backup_{engine}_{timestamp}.sql.gz"

        # Only local storage is implemented; cloud choices in Backup Settings
        # are accepted but fall back to local until a cloud backend is added.
        storage = get_storage_backend("local")
        file_path = storage.save(file_name, compressed)

        record.file_name = file_name
        record.file_path = file_path
        record.file_size = len(compressed)
        record.storage_location = "local"
        record.status = "success"
        record.completed_at = timezone.now()
        record.save()

        _apply_retention_policy()
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)[:4000]
        record.completed_at = timezone.now()
        record.save()
    return record


def _apply_retention_policy():
    from .models import BackupRecord, BackupSettings

    keep = BackupSettings.get_solo().retention_count
    storage = get_storage_backend("local")
    stale_records = BackupRecord.objects.filter(status="success").order_by("-started_at")[keep:]
    for record in stale_records:
        storage.delete(record.file_path)
        record.delete()


def restore_backup(backup_record, initiated_by=None):
    from .models import RestoreLog

    current_engine = get_db_engine()
    restore_log = RestoreLog.objects.create(
        backup_record=backup_record, initiated_by=initiated_by, status="in_progress"
    )

    if backup_record.db_engine != current_engine:
        restore_log.status = "failed"
        restore_log.error_message = (
            f"This backup was created on a {backup_record.db_engine} database, but the server "
            f"is currently running {current_engine}. Restore refused."
        )
        restore_log.completed_at = timezone.now()
        restore_log.save()
        return restore_log

    try:
        pre_restore_record = create_backup(initiated_by=initiated_by, backup_type="pre_restore")
        if pre_restore_record.status != "success":
            raise BackupError(f"Could not take a safety backup before restoring: {pre_restore_record.error_message}")
        restore_log.pre_restore_backup = pre_restore_record
        restore_log.save(update_fields=["pre_restore_backup"])

        storage = get_storage_backend("local")
        with storage.open_for_download(backup_record.file_path) as f:
            compressed = f.read()
        raw_bytes = gzip.decompress(compressed)

        if current_engine == "sqlite":
            _restore_sqlite(raw_bytes)
        elif current_engine == "postgresql":
            _restore_postgres(settings.DATABASES["default"], raw_bytes)
        else:
            raise BackupError(f"Unsupported database engine: {current_engine}")

        restore_log.status = "success"
        restore_log.completed_at = timezone.now()
        restore_log.save()
    except Exception as exc:
        restore_log.status = "failed"
        restore_log.error_message = str(exc)[:4000]
        restore_log.completed_at = timezone.now()
        restore_log.save()
    return restore_log
