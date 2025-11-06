@echo off
echo Starting Download-Only Mode...
echo ================================
echo This will download videos, extract metadata, generate thumbnails,
echo and update the database and sheets WITHOUT transcription or uploads.
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the download-only script
echo Starting download process...
python download_only.py

echo.
echo Download process completed!
pause
