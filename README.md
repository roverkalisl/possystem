# possystem

## Sample Data

To populate the app with sample data, run:

```bash
python manage.py populate_sample_data
```

This creates sample categories, suppliers, customers, items, a purchase order, a GRN, a sale, and a return.

## Automatic Backups on Windows

The backup setting controls whether a backup is due; it does not create an operating-system schedule. Register the Windows Task Scheduler task once from PowerShell:

```powershell
Set-Location "C:\P&I Constructions\NewPOSSystem\pos_system"
.\register_scheduled_backup.ps1
```

The task invokes `python manage.py run_scheduled_backup` every 15 minutes. The command checks the configured backup frequency and time before creating a backup. To use another interval or project location:

```powershell
.\register_scheduled_backup.ps1 -ProjectPath "C:\path\to\pos_system" -IntervalMinutes 15
```

To remove the scheduled task:

```powershell
Unregister-ScheduledTask -TaskName "POS System Scheduled Backup" -Confirm:$false
```

### Render Production Cron

The repository includes [render.yaml](render.yaml), which defines a Render Cron Job that runs `python manage.py run_scheduled_backup` every 15 minutes. Configure the `DATABASE_URL`, `SECRET_KEY`, and Google Drive variables in Render; the Cron Job must use the same PostgreSQL database as the web service.

Render cron expressions are evaluated in UTC. The command uses Django's configured `TIME_ZONE` (`Asia/Colombo`) when comparing `Backup Time`, so the configured business time is honored whenever the 15-minute UTC poll reaches it. A missed poll is not run retroactively.

The PostgreSQL client utility `pg_dump` must be available in the Cron Job runtime because PostgreSQL backups use the existing `backup_engine.py` implementation.
