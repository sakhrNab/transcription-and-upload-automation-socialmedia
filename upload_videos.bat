@echo off
echo Starting Upload-Only Mode...
echo ================================
echo This will upload videos from assets/finished_videos/ to Google Drive
echo and AIWaverider, then update the database and sheets.
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the upload-only script
echo Starting upload process...
python upload_only.py

echo.
echo Upload process completed!
pause
