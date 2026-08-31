import io
import os

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404

from .backup_storage import get_storage_backend, StorageUnavailableError
from .models import BackupRecord, BackupSettings, RestoreLog
from .backup_engine import create_backup, restore_backup, get_db_engine, compute_next_scheduled
from .views import is_owner


@user_passes_test(is_owner)
def backup_dashboard(request):
    last_backup = BackupRecord.objects.filter(backup_type__in=["manual", "scheduled"]).order_by("-started_at").first()
    settings_row = BackupSettings.get_solo()
    recent_backups = BackupRecord.objects.order_by("-started_at")[:5]
    try:
        drive_status = get_storage_backend("google_drive").status()
    except Exception:
        drive_status = "not_configured"
    return render(request, "pos/backup_dashboard.html", {
        "last_backup": last_backup,
        "settings_row": settings_row,
        "recent_backups": recent_backups,
        "next_scheduled": compute_next_scheduled(settings_row),
        "db_engine": get_db_engine(),
        "google_drive_status": drive_status,
    })


@user_passes_test(is_owner)
def create_backup_now(request):
    if request.method == "POST":
        record = create_backup(initiated_by=request.user, backup_type="manual")
        if record.status == "success":
            messages.success(request, f"Backup created successfully: {record.file_name} ({record.file_size_display}).")
        else:
            messages.error(request, f"Backup failed: {record.error_message}")
    return redirect("backup_dashboard")


@user_passes_test(is_owner)
def backup_history(request):
    records = BackupRecord.objects.all().select_related("initiated_by").order_by("-started_at")

    status = request.GET.get("status")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status:
        records = records.filter(status=status)
    if date_from:
        records = records.filter(started_at__date__gte=date_from)
    if date_to:
        records = records.filter(started_at__date__lte=date_to)

    return render(request, "pos/backup_history.html", {
        "records": records[:200],
        "status_filter": status or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    })


@user_passes_test(is_owner)
def download_backup(request, backup_id):
    record = get_object_or_404(BackupRecord, id=backup_id)
    if record.status != "success" or not record.file_path:
        messages.error(request, "This backup file is not available for download.")
        return redirect("backup_history")

    try:
        storage = get_storage_backend(record.storage_location or "local")
        with storage.open_for_download(record.file_path, record) as backup_file:
            payload = backup_file.read()
        response = FileResponse(io.BytesIO(payload), as_attachment=True, filename=record.file_name)
        return response
    except (StorageUnavailableError, FileNotFoundError, OSError, ValueError) as exc:
        messages.error(request, f"This backup file could not be downloaded: {exc}")
        return redirect("backup_history")


@user_passes_test(is_owner)
def delete_backup(request, backup_id):
    record = get_object_or_404(BackupRecord, id=backup_id)
    if request.method == "POST":
        if record.status == "in_progress":
            messages.error(request, "Cannot delete a backup that is still in progress.")
        else:
            try:
                storage = get_storage_backend(record.storage_location or "local")
                storage.delete(record.file_path, record)
            except Exception:
                messages.error(request, "Backup deletion failed on the configured storage backend.")
                return redirect("backup_history")
            record.delete()
            messages.success(request, "Backup deleted.")
    return redirect("backup_history")


@user_passes_test(is_owner)
def restore_database(request):
    available_backups = BackupRecord.objects.filter(status="success").order_by("-started_at")
    recent_restores = RestoreLog.objects.select_related("backup_record", "initiated_by").order_by("-started_at")[:10]

    if request.method == "POST":
        backup_id = request.POST.get("backup_id")
        confirmation = (request.POST.get("confirmation") or "").strip()

        record = get_object_or_404(BackupRecord, id=backup_id, status="success")

        if confirmation != "RESTORE":
            messages.error(request, 'Restore cancelled — you must type "RESTORE" exactly to confirm.')
            return redirect("restore_database")

        restore_log = restore_backup(record, initiated_by=request.user)
        if restore_log.status == "success":
            messages.success(
                request,
                f"Database restored successfully from {record.file_name}. "
                f"A safety backup of the previous state was created automatically."
            )
        else:
            messages.error(request, f"Restore failed: {restore_log.error_message}")
        return redirect("restore_database")

    return render(request, "pos/restore_database.html", {
        "available_backups": available_backups,
        "recent_restores": recent_restores,
        "db_engine": get_db_engine(),
    })


@user_passes_test(is_owner)
def backup_settings_view(request):
    settings_row = BackupSettings.get_solo()

    if request.method == "POST":
        settings_row.frequency = request.POST.get("frequency") or settings_row.frequency
        backup_time = request.POST.get("backup_time")
        if backup_time:
            settings_row.backup_time = backup_time
        settings_row.weekly_day = int(request.POST.get("weekly_day") or settings_row.weekly_day)
        settings_row.monthly_day = int(request.POST.get("monthly_day") or settings_row.monthly_day)
        settings_row.retention_count = int(request.POST.get("retention_count") or settings_row.retention_count)
        settings_row.auto_backup_enabled = request.POST.get("auto_backup_enabled") == "on"
        settings_row.storage_location = request.POST.get("storage_location") or settings_row.storage_location
        settings_row.save()
        messages.success(request, "Backup settings updated.")
        return redirect("backup_settings")

    return render(request, "pos/backup_settings.html", {
        "settings_row": settings_row,
        "next_scheduled": compute_next_scheduled(settings_row),
    })
