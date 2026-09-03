[CmdletBinding()]
param(
    [string]$ProjectPath = $PSScriptRoot,
    [string]$TaskName = "POS System Scheduled Backup",
    [int]$IntervalMinutes = 15
)

$pythonPath = Join-Path $ProjectPath ".venv\Scripts\python.exe"
$managePath = Join-Path $ProjectPath "manage.py"

if (-not (Test-Path $pythonPath)) {
    throw "Virtualenv Python was not found at $pythonPath"
}
if (-not (Test-Path $managePath)) {
    throw "Django manage.py was not found at $managePath"
}
if ($IntervalMinutes -lt 1) {
    throw "IntervalMinutes must be at least 1."
}

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$managePath`" run_scheduled_backup" `
    -WorkingDirectory $ProjectPath
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Description "Invokes the POS System scheduled backup command. Backup settings decide whether a backup is due." `
    -Force | Out-Null

Write-Host "Registered '$TaskName' to run every $IntervalMinutes minutes."
Write-Host "The Django command will perform a backup only when Backup Settings say one is due."
Write-Host "Enable Automatic Backup in the application Backup Settings page."
