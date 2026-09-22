@echo off
echo Starting Continuous Video Upload Scanner...
echo.
echo This will monitor assets/finished_videos/ for new videos
echo and automatically upload them to Google Drive and AIWaverider.
echo.
echo Press Ctrl+C to stop the scanner.
echo.
.venv\Scripts\python.exe continuous_scanner.py
pause
