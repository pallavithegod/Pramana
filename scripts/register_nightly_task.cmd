@echo off
rem Registers the nightly collection in Windows Task Scheduler (00:20 IST daily).
rem Re-run any time; /F overwrites. Laptop must be awake at trigger time --
rem enable "wake the computer to run this task" in Task Scheduler UI if desired.
schtasks /Create /F /SC DAILY /ST 00:20 /TN "AirSankhyiki Nightly Collection" ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"D:\Engineering Resources\SIH 26\project\air-sankhyiki\scripts\nightly_collect.ps1\""
echo.
echo Registered. Test immediately with:
echo   schtasks /Run /TN "AirSankhyiki Nightly Collection"
