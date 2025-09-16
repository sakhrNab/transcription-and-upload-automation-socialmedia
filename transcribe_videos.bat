@echo off
echo Starting Transcribe-Only Mode...
echo ===================================
echo This will transcribe downloaded videos using GPU acceleration,
echo generate smart names, and update the database and sheets.
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the transcribe-only script
echo Starting transcription process...
python transcribe_only.py

echo.
echo Transcription process completed!
pause

