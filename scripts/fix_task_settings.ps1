# Task conditions for the nightly collection. NOTE: New-ScheduledTaskSettingsSet
# resets unspecified settings to DEFAULTS — and the default is "do not start on
# battery", which silently skipped the 6 Sep run on an unplugged laptop. Always
# set the full set together.
$s = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -WakeToRun `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Set-ScheduledTask -TaskName 'AirSankhyiki Nightly Collection' -Settings $s | Out-Null
$t = (Get-ScheduledTask -TaskName 'AirSankhyiki Nightly Collection').Settings
$t | Select-Object StartWhenAvailable, WakeToRun, DisallowStartIfOnBatteries, StopIfGoingOnBatteries, ExecutionTimeLimit
