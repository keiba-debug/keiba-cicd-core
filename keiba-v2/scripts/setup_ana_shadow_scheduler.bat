@echo off
REM ============================================
REM Register Task Scheduler entries for ana-tansho shadow sleeve (Session 169)
REM   KeibaCICD_ana_shadow_log    : daily 09:30, repeat /1min for 7h (->16:30), hidden, mode=log
REM   KeibaCICD_ana_shadow_settle : daily 23:00, mode=settle (haraimodoshi payouts in DB by then)
REM PAPER ONLY (no real money). Run THIS as Administrator (schtasks /create needs it).
REM ============================================
setlocal
set VBS=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\ana_shadow_hidden.vbs

schtasks /query /tn "KeibaCICD_ana_shadow_log" >nul 2>&1
if %errorlevel%==0 schtasks /delete /tn "KeibaCICD_ana_shadow_log" /f
schtasks /create ^
    /tn "KeibaCICD_ana_shadow_log" ^
    /tr "wscript.exe \"%VBS%\" log" ^
    /sc daily ^
    /st 09:30 ^
    /ri 5 ^
    /du 07:00 ^
    /f

schtasks /query /tn "KeibaCICD_ana_shadow_settle" >nul 2>&1
if %errorlevel%==0 schtasks /delete /tn "KeibaCICD_ana_shadow_settle" /f
schtasks /create ^
    /tn "KeibaCICD_ana_shadow_settle" ^
    /tr "wscript.exe \"%VBS%\" settle" ^
    /sc daily ^
    /st 23:00 ^
    /f

echo.
echo === registered ===
schtasks /query /tn "KeibaCICD_ana_shadow_log" /fo list 2>nul | findstr /C:"TaskName" /C:"Status" /C:"Next Run"
schtasks /query /tn "KeibaCICD_ana_shadow_settle" /fo list 2>nul | findstr /C:"TaskName" /C:"Status" /C:"Next Run"
endlocal
