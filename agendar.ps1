$ErrorActionPreference = "Stop"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $appDir "nfse_app.py"
$configPath = Join-Path $appDir "agendamento.json"
$taskName = "Coleta XML NFSE"

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Não encontrei nfse_app.py nesta pasta. Extraia todos os arquivos juntos."
}
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Crie o arquivo agendamento.json (use agendamento.example.json como modelo)."
}

$cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if (-not $cfg.pfx -or -not $cfg.password_file -or -not $cfg.cnpjs) {
    throw "O agendamento.json precisa de 'pfx', 'password_file' e 'cnpjs'."
}
if (-not (Test-Path -LiteralPath $cfg.pfx)) {
    throw "Certificado não encontrado: $($cfg.pfx)"
}
if (-not (Test-Path -LiteralPath $cfg.password_file)) {
    throw "Arquivo de senha não encontrado: $($cfg.password_file)"
}

$pythonExe = Join-Path $appDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    try { $pythonExe = (& py -3 -c "import sys; print(sys.executable)").Trim() }
    catch { $pythonExe = (& python -c "import sys; print(sys.executable)").Trim() }
}
if (-not $pythonExe -or -not (Test-Path -LiteralPath $pythonExe)) {
    throw "Não encontrei o Python do app. Execute iniciar.bat antes de agendar."
}
& $pythonExe -c "import requests, cryptography"
if ($LASTEXITCODE -ne 0) {
    throw "As dependências não estão instaladas. Execute instalar.bat."
}
$pythonwExe = Join-Path (Split-Path -Parent $pythonExe) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonwExe)) { $pythonwExe = $pythonExe }

Write-Host "Escolha a frequência:"
Write-Host "1 - Todos os dias"
Write-Host "2 - Segunda a sexta"
Write-Host "3 - Uma vez por semana"
Write-Host "4 - A cada hora"
$frequency = Read-Host "Opção (1-4)"
if ($frequency -notin @("1", "2", "3", "4")) { throw "Opção inválida." }

$taskTime = $null
if ($frequency -ne "4") {
    $timeText = Read-Host "Horário (HH:mm, exemplo 07:00)"
    try { $taskTime = [datetime]::ParseExact($timeText, "HH:mm", [Globalization.CultureInfo]::InvariantCulture) }
    catch { throw "Horário inválido. Use o formato HH:mm, por exemplo 07:00." }
}

$argument = '"' + $scriptPath + '" run --config "' + $configPath + '"'
$action = New-ScheduledTaskAction -Execute $pythonwExe -Argument $argument -WorkingDirectory $appDir
switch ($frequency) {
    "1" { $trigger = New-ScheduledTaskTrigger -Daily -At $taskTime }
    "2" { $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $taskTime }
    "3" {
        $dayText = Read-Host "Dia da semana (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday ou Sunday)"
        try { $day = [System.Enum]::Parse([System.DayOfWeek], $dayText, $true) }
        catch { throw "Dia da semana inválido." }
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $day -At $taskTime
    }
    "4" {
        $startAt = (Get-Date).AddMinutes(2)
        $trigger = New-ScheduledTaskTrigger -Once -At $startAt -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
    }
}

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Agendamento criado: $taskName"
Write-Host "O app roda sem janela quando sua conta do Windows estiver conectada."
Write-Host "Logs: %LOCALAPPDATA%\ColetaXmlNFSE\logs"
Read-Host "Pressione Enter para fechar"
