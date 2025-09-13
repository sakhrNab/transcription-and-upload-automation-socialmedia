Social Media Content Processor & Tracker

A comprehensive Python utility that orchestrates the entire social media content workflow: downloads videos (TikTok/Instagram/etc.) via yt-dlp, converts to audio, transcribes using Whisper, generates thumbnails, uploads to both Google Drive and AIWaverider Drive, and maintains a master tracking sheet with real-time status updates.

## Features

### Core Processing
- Download video from a URL using `yt_dlp`
- Convert video to WAV using `ffmpeg`
- Transcribe audio using Whisper
- Generate thumbnails automatically
- Batch-mode: read multiple URLs from a text file (`--urls-file`)

### Dual Upload System
- **Google Drive**: Upload videos, thumbnails, and Excel workbooks
- **AIWaverider Drive**: Upload videos to `/videos/instagram/ai.uprise/` and thumbnails to `/thumbnails/instagram/`

### Master Tracking System
- **Google Sheets Integration**: Real-time tracking sheet with all content status
- **Local Backup**: Automatic local backup to `downloads/socialmedia/tracking/`
- **Smart Updates**: Updates existing entries, appends new ones (never overwrites existing data)
- **Thumbnail Display**: Actual thumbnail images displayed in the tracking sheet

### Automation & Monitoring
- **Continuous Monitoring**: Automatic detection of new videos and thumbnails
- **State Management**: Tracks upload status across all platforms
- **Error Handling**: Robust error handling with detailed logging
- **Offline Mode**: Continues working even when Google services are unavailable

## Core Scripts and Files

### Main Scripts
- `main.py` — **Main entry point** for easy system access
- `core/social_media_processor.py` — **Master orchestrator script** that runs the entire workflow
- `core/full-rounded-url-download-transcription.py` — Downloads and processes videos
- `scripts/upload-new-video-to-google.py` — Continuous monitor for uploading MP4 files to Google Drive
- `scripts/upload-thumbnails-to-google.py` — Handles thumbnail uploads to Google Drive

### Configuration Files
- `requirements.txt` — Python dependencies (install into a venv)
- `credentials.json` — Google API client credentials
- `token.json` — OAuth token (automatically refreshed/overwritten)
- `.env` — Environment variables and API keys

### State & Tracking Files
- `state.json` — Tracks video upload status to Google Drive
- `state-thumbnails.json` — Tracks thumbnail upload status to Google Drive
- `master_sheet_backup.json` — Local backup of Google Sheets data
- `downloads/socialmedia/tracking/` — Local tracking data (JSON & CSV)

### Output Directories
- `downloads/videos/` — Downloaded video files
- `downloads/audio/` — Extracted audio files
- `downloads/thumbnails/` — Generated thumbnail images
- `downloads/transcripts/` — Transcription files and Excel workbook
- `finished_videos/` — Processed videos ready for upload

## Environment Variables (.env)

### Required API Keys
- `OPENAI_API_KEY` (required) — OpenAI API key for GPT-4o-mini naming
- `AIWAVERIDER_DRIVE_TOKEN` (required) — Bearer token for AIWaverider Drive API
- `UPLOAD_FILE_AIWAVERIDER` (required) — AIWaverider upload endpoint URL

### Google Services
- `GOOGLE_CREDENTIALS_FILE` (optional) — default: `credentials.json`
- `GOOGLE_TOKEN_FILE` (optional) — default: `token.json`
- `MASTER_SHEET_ID` (required) — Google Sheets ID for master tracking

### Directory Configuration
- `VIDEO_OUTPUT_DIR` (optional) — default: `downloads/videos`
- `AUDIO_OUTPUT_DIR` (optional) — default: `downloads/audio`
- `THUMBNAILS_DIR` (optional) — default: `downloads/thumbnails`
- `TRANSCRIPTS_DIR` (optional) — default: `downloads/transcripts`
- `FOLDER_TO_WATCH` (optional) — folder to monitor for videos, default: `finished_videos`

### Upload Configuration
- `THUMBNAILS_DRIVE_FOLDER_ID` (optional) — Google Drive folder ID for thumbnails
- `DRIVE_FOLDER` (optional) — Google Drive folder name, default: 'AIWaverider'

### Excel Configuration
- `EXCEL_FILENAME` (optional) — default: `video_transcripts.xlsx`
- `EXCEL_FILE_PATH` (optional) — full path to the Excel file

### Example `.env`:

```text
# Required API Keys
OPENAI_API_KEY=sk-proj-...
AIWAVERIDER_DRIVE_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
UPLOAD_FILE_AIWAVERIDER=https://drive-backend.aiwaverider.com/webhook/files/upload

# Google Services
MASTER_SHEET_ID=1HNKPIhq1kB1xoS52cM2U7KOdiJS8pqiQ7j_fbTQOUPI
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json

# Directory Configuration
VIDEO_OUTPUT_DIR=downloads/videos
AUDIO_OUTPUT_DIR=downloads/audio
THUMBNAILS_DIR=downloads/thumbnails
TRANSCRIPTS_DIR=downloads/transcripts
FOLDER_TO_WATCH=finished_videos

# Upload Configuration
THUMBNAILS_DRIVE_FOLDER_ID=1iUmCVkX863MqyvJIZ_aWbi9toEI39X8Z
DRIVE_FOLDER=AIWaverider

# Excel Configuration
EXCEL_FILENAME=video_transcripts.xlsx
```

## Install
Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(If `requirements.txt` is not updated, ensure you have: `yt-dlp`, `ffmpeg-python`, `openai`, `whisper` or `openai-whisper` as used, `openpyxl`, `python-dotenv`, `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`, `pydub`, `torch`.)

## Usage

### Master Script (Recommended)
Run the complete workflow with a single command:
```powershell
python main.py
```

Or run the core processor directly:
```powershell
python core\social_media_processor.py
```

This will:
1. Process all URLs from `urls.txt`
2. Download videos and generate thumbnails
3. Upload to Google Drive
4. Upload to AIWaverider Drive
5. Update the master tracking sheet
6. Save local backups

### Individual Scripts

#### Video Processing
Process videos in batch mode from `urls.txt`:
```powershell
python .\full-rounded-url-download-transcription.py --urls-file urls.txt
```

Single URL mode:
```powershell
python .\full-rounded-url-download-transcription.py --url "https://www.tiktok.com/...?"
```

#### Upload Monitors
Start the continuous video upload monitor:
```powershell
python .\upload-new-video-to-google.py
```

Upload thumbnails to Google Drive:
```powershell
python .\upload-thumbnails-to-google.py
```

### Workflow Overview
1. **Download & Process**: Videos are downloaded, converted to audio, and transcribed
2. **Thumbnail Generation**: Automatic thumbnail creation from video frames
3. **Dual Upload**: Content uploaded to both Google Drive and AIWaverider Drive
4. **Master Tracking**: Real-time status updates in Google Sheets
5. **Local Backup**: All data saved locally for offline access

## Master Tracking System

The system includes a comprehensive tracking system that monitors all content across platforms:

### Google Sheets Integration
- **Real-time Updates**: Automatic status updates for all uploads
- **Thumbnail Display**: Actual thumbnail images displayed in the sheet
- **Smart Updates**: Updates existing entries, appends new ones (never overwrites)
- **Column Structure**: Tracks drive IDs, filenames, upload times, and status across platforms

### Local Backup System
- **Automatic Backup**: All data saved to `downloads/socialmedia/tracking/`
- **Multiple Formats**: Data saved as both JSON and CSV
- **Offline Mode**: Continues working when Google services are unavailable
- **Data Recovery**: Local backups can be used to restore lost data

### AIWaverider Drive Integration
- **Dual Upload**: Content uploaded to both Google Drive and AIWaverider Drive
- **Duplicate Prevention**: Automatically checks existing files before uploading to prevent duplicates
- **Smart File Checking**: Uses `/api/files/list` endpoint to efficiently check existing files
- **Chunked Upload Support**: Large files (>10MB) use chunked upload for better reliability
- **Organized Structure**: 
  - Videos: `/videos/instagram/ai.uprise/`
  - Thumbnails: `/thumbnails/instagram/`
- **Authentication**: Uses Bearer token authentication
- **Error Handling**: Robust error handling with detailed logging

### State Management
- **Video Tracking**: `state.json` tracks video upload status to Google Drive
- **Thumbnail Tracking**: `state-thumbnails.json` tracks thumbnail upload status
- **Master Backup**: `master_sheet_backup.json` backs up Google Sheets data
- **Persistent State**: State files persist across runs for efficient processing

### Efficiency Features
- **Duplicate Prevention**: Skips files already uploaded to AIWaverider Drive
- **Bulk File Checking**: Single API call to check all existing files instead of individual checks
- **Incremental Processing**: Only processes new or changed content
- **Smart Upload Logic**: 
  - Files <10MB: Regular upload
  - Files ≥10MB: Chunked upload for reliability
- **State Persistence**: Avoids re-processing completed tasks
- **Offline Mode**: Continues working with local backups when services are unavailable

## Google OAuth / tokens
- Place `credentials.json` (Google API client credentials) in the repo root.
- On first run the script opens a local browser to complete OAuth and creates `token.json`.
- If `token.json` expires the script will try to refresh it and overwrite `token.json`; if refresh fails it will perform the OAuth flow again and save the new token.

## Handling a corrupt Excel file
If the script detects the existing Excel file is invalid (unsupported or corrupted), it will move the bad file to `transcripts.xlsx.invalid_<timestamp>` and create a fresh workbook with the header row. You can inspect the moved file later.

(change location is inside `transcribe-videos.py` where `load_workbook(excel_path)` is attempted — the script now catches `openpyxl.utils.exceptions.InvalidFileException` and renames the bad file)

## How videos are fetched
Video downloading/fetching is handled by `yt_dlp` (`download_video()` inside `transcribe-videos.py`). `yt_dlp` supports many sites (TikTok, Instagram, YouTube, etc.) and chooses the best available formats; the script requests `mp4` format and saves it to `VIDEO_OUTPUT_DIR`.

## Troubleshooting

### Common Issues

#### Authentication Errors
- **Google OAuth**: Ensure `credentials.json` is present and `token.json` is valid
- **AIWaverider Token**: Check `AIWAVERIDER_DRIVE_TOKEN` in `.env` file
- **Sheet Access**: Verify `MASTER_SHEET_ID` is correct and sheet exists

#### Upload Issues
- **Google Drive**: Check folder permissions and available storage
- **AIWaverider Drive**: Verify API endpoint and token validity
- **Large Files**: Video uploads may timeout; check network connection

#### Data Issues
- **Excel Corruption**: Script will automatically backup and recreate corrupted files
- **Missing State Files**: Script will create new state files if missing
- **Sheet Updates**: Existing data is never overwritten; new data is appended

#### Performance Issues
- **Memory Usage**: Large videos may require more RAM
- **Network Timeouts**: Increase timeout values in configuration
- **Concurrent Uploads**: Script handles uploads sequentially to avoid conflicts

### Error Recovery
- **Offline Mode**: Script continues working with local backups when services are unavailable
- **State Recovery**: Delete state files to force re-upload of all content
- **Sheet Recovery**: Use local backup files to restore lost data

### Debug Mode
Enable detailed logging by setting `LOG_LEVEL=DEBUG` in `.env` file.

## Advanced Features

### Smart Data Management
- **Incremental Updates**: Only processes new or changed content
- **State Persistence**: Maintains state across runs for efficiency
- **Conflict Resolution**: Handles duplicate content gracefully
- **Data Integrity**: Validates data before uploading

### Monitoring & Logging
- **Comprehensive Logging**: Detailed logs for all operations
- **Progress Tracking**: Real-time status updates
- **Error Reporting**: Detailed error messages with context
- **Performance Metrics**: Tracks processing times and success rates

### Scalability
- **Batch Processing**: Handles multiple videos efficiently
- **Resource Management**: Optimized memory and CPU usage
- **Network Optimization**: Efficient upload strategies
- **Error Recovery**: Automatic retry mechanisms

## Efficiency Optimizations

### Current Optimizations
- **Duplicate Prevention**: Prevents unnecessary uploads by checking existing files
- **Bulk API Calls**: Single file list check instead of individual file checks
- **Chunked Uploads**: Reliable uploads for large files with automatic retry
- **State Persistence**: Avoids re-processing completed tasks
- **Smart File Detection**: Only processes files that have been uploaded to Google Drive

### Potential Future Improvements
- **Parallel Processing**: Upload multiple files simultaneously (with rate limiting)
- **Concurrent API Calls**: Run Google Drive and AIWaverider uploads in parallel
- **Caching**: Cache file lists locally to reduce API calls
- **Delta Processing**: Only check for changes since last run
- **Batch Operations**: Group multiple operations into single API calls where possible
- **Connection Pooling**: Reuse HTTP connections for better performance
- **Progress Tracking**: Real-time progress indicators for long-running operations

## Optional Improvements
- Add `--no-upload` to skip uploads for testing
- Add parallel processing for faster batch operations
- Implement webhook notifications for upload completion
- Add support for additional video platforms
- Implement content scheduling and automation

## License
No license specified — treat this repository as private/internal unless you add a license file.


