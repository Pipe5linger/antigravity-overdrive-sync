$actionSync = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"D:\AI\Projects\antigravity-overdrive-sync\sync_silent.vbs"'
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$triggerHourly = New-ScheduledTaskTrigger -At (Get-Date) -Once -RepetitionInterval (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName 'ULM_Memory_Sync' -Action $actionSync -Trigger @($triggerLogon, $triggerHourly) -Force

$actionDaemon = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"D:\AI\Projects\antigravity-overdrive-sync\daemon_silent.vbs"'
Register-ScheduledTask -TaskName 'ULM_Daemon_Startup' -Action $actionDaemon -Trigger $triggerLogon -Force

Write-Host "[+] Successfully registered ULM_Memory_Sync and ULM_Daemon_Startup with AtLogOn boot triggers!"
