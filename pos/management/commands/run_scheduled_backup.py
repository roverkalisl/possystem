"""Self-throttling scheduled backup runner.

This project has no Celery/Redis, so scheduling is done the simple way: this
command is meant to be invoked frequently (e.g. every 15 minutes) by one OS
cron / Task Scheduler entry, and it decides for itself whether a backup is
actually due based on BackupSettings + the most recent scheduled backup, so
it's safe to call it far more often than backups should actually run.

Example cron entry (Linux/production):
    */15 * * * * cd /path/to/app && /path/to/venv/bin/python manage.py run_scheduled_backup

Example Windows Task Scheduler action (this dev machine, if desired):
    Program: C:\\path\\to\\.venv\\Scripts\\python.exe
    Arguments: manage.py run_scheduled_backup
    Start in: C:\\P&I Constructions\\NewPOSSystem\\pos_system
    Trigger: repeat every 15 minutes
"""
import calendar
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pos.backup_engine import create_backup
from pos.models import BackupExecutionLock, BackupRecord, BackupSettings


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs a scheduled backup if one is due per Backup Settings. Safe to invoke frequently."

    def handle(self, *args, **options):
        started_at = timezone.localtime()
        self._log("Scheduled backup check started", started_at)

        with transaction.atomic():
            lock, _ = BackupExecutionLock.objects.get_or_create(id=1)
            locked = BackupExecutionLock.objects.select_for_update().get(pk=lock.pk)
            settings_row = BackupSettings.get_solo()

            if not settings_row.auto_backup_enabled:
                message = "Automatic backup is disabled in Backup Settings. Nothing to do."
                self._log(f"Backup skipped: {message}", started_at)
                return

            now = timezone.localtime()

            if not self._is_due(settings_row, now):
                self._log("Backup not due, skipped", now)
                return

            if self._already_ran_this_period(settings_row, now):
                self._log("Backup already completed for this period, skipped", now)
                return

            self._log("Backup due; scheduled backup started", now)
            record = create_backup(initiated_by=None, backup_type="scheduled")
            if record.status == "success":
                self._log(f"Scheduled backup completed successfully: {record.file_name} ({record.file_size_display})", timezone.localtime(), success=True)
            else:
                self._log(f"Scheduled backup failed: {record.error_message}", timezone.localtime(), error=True)

    def _log(self, message, at, success=False, error=False):
        line = f"{at.strftime('%Y-%m-%d %H:%M')} - {message}"
        logger.log(logging.ERROR if error else logging.INFO, line)
        if success:
            self.stdout.write(self.style.SUCCESS(line))
        elif error:
            self.stdout.write(self.style.ERROR(line))
        else:
            self.stdout.write(line)

    def _is_due(self, settings_row, now):
        if now.time() < settings_row.backup_time:
            return False
        if settings_row.frequency == "weekly" and now.weekday() != settings_row.weekly_day:
            return False
        if settings_row.frequency == "monthly":
            last_day_of_month = calendar.monthrange(now.year, now.month)[1]
            target_day = min(settings_row.monthly_day, last_day_of_month)
            if now.day != target_day:
                return False
        return True

    def _already_ran_this_period(self, settings_row, now):
        last_scheduled = (
            BackupRecord.objects.filter(backup_type="scheduled", status="success")
            .order_by("-started_at")
            .first()
        )
        if not last_scheduled:
            return False

        last_local = timezone.localtime(last_scheduled.started_at)

        if settings_row.frequency == "daily":
            return last_local.date() == now.date()
        if settings_row.frequency == "weekly":
            return last_local.isocalendar()[:2] == now.isocalendar()[:2]
        if settings_row.frequency == "monthly":
            return (last_local.year, last_local.month) == (now.year, now.month)
        return False
