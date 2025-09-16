@echo off
echo Starting Social Media Content Processor Web UI...
echo.

REM Activate virtual environment
call ..\.venv\Scripts\activate.bat

REM Install web UI requirements
pip install -r requirements.txt

REM Start the Flask server
python app.py

pause
