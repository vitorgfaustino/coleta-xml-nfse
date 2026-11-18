$taskName = "Coleta XML NFSE"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Agendamento removido (se existia)."
Read-Host "Pressione Enter para fechar"
