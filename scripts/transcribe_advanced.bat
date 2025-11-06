@echo off
echo Starting Advanced Transcribe Mode...
echo =====================================
echo This provides advanced filtering and selection options
echo for video transcription with GPU acceleration.
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Show usage examples
echo Usage examples:
echo   python transcribe_specific.py --list
echo   python transcribe_specific.py --all-pending --max-videos 5
echo   python transcribe_specific.py --video-ids dQw4w9WgXcQ DOEATowCJuJ
echo   python transcribe_specific.py --pattern rick --status PENDING
echo   python transcribe_specific.py --recent --max-videos 3
echo.

REM Run the advanced transcribe script
echo Starting advanced transcription process...
python transcribe_specific.py %*

echo.
echo Advanced transcription process completed!
pause

