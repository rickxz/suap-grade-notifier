<#
.SYNOPSIS
  Instala o SUAP Grade Notifier no Windows e agenda a verificação a cada 30 minutos.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Uninstall
#>
param(
    [string]$Source = (Resolve-Path "$PSScriptRoot\.."),
    [int]$IntervalMinutes = 30,
    [switch]$SkipSetup,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "SUAP Grade Notifier"
$AppDir = Join-Path $env:LOCALAPPDATA "suap-notifier"
$Venv = Join-Path $AppDir "venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$PythonW = Join-Path $Venv "Scripts\pythonw.exe"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path $Python) {
        & $Python -c "import keyring; from suap_notifier.app import KEYRING_SERVICE as s, KEYRING_USER_ENTRY as u; p = keyring.get_password(s, u); [keyring.delete_password(s, k) for k in (p, u) if k and keyring.get_password(s, k)]"
    }
    Remove-Item -Recurse -Force $AppDir -ErrorAction SilentlyContinue
    Write-Host "Desinstalado: tarefa, senha salva e dados em $AppDir removidos."
    exit 0
}

if (-not (Test-Path $Python)) {
    Write-Host "Criando ambiente Python em $Venv..."
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $Venv } else { & python -m venv $Venv }
    if ($LASTEXITCODE -ne 0) { throw "não foi possível criar o ambiente Python (o Python está instalado?)" }
}

Write-Host "Instalando a partir de $Source..."
& $Python -m pip install --quiet --upgrade pip
& $Python -m pip install --quiet --upgrade $Source
if ($LASTEXITCODE -ne 0) { throw "pip install falhou" }

if (-not $SkipSetup) {
    & $Python -m suap_notifier setup
    if ($LASTEXITCODE -ne 0) { throw "setup falhou" }
}

$action = New-ScheduledTaskAction -Execute $PythonW -Argument "-m suap_notifier run" -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
# An AtLogOn trigger can't take an interval directly, so borrow the repetition pattern from a -Once trigger
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)).Repetition
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Tarefa '$TaskName' agendada: ao entrar no Windows e a cada $IntervalMinutes minutos."
Write-Host "Log: $AppDir\notifier.log"
