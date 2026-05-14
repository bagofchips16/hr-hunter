@echo off
REM Setup daily scheduled task for HR Hunter
schtasks /create /tn "HRHunter_DailyScan" /tr "C:\Users\kkumari\Projects\hr-hunter\venv\Scripts\python.exe C:\Users\kkumari\Projects\hr-hunter\daily_run.py" /sc daily /st 08:30 /f
echo Task "HRHunter_DailyScan" created — runs daily at 8:30 AM
pause
