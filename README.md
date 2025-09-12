Transcribe & Upload Videos to Google Drive

A small Python utility that downloads a single video (TikTok/Instagram/etc.) via yt-dlp, converts it to audio, transcribes it using Whisper, appends metadata and transcript to an Excel workbook, and uploads the workbook to Google Drive.

## Features
- Download video from a URL using `yt_dlp`.
- Convert video to WAV using `ffmpeg`.
- Transcribe audio using Whisper.
- Append a row per video to an Excel workbook (`.xlsx`) using `openpyxl`.
- Upload the Excel workbook to Google Drive (OAuth2).
- Batch-mode: read multiple URLs from a text file (`--urls-file`).
- Automatic handling: if an existing Excel file is invalid/corrupt, the script will move it aside and create a fresh workbook.

## Files of interest
- `transcribe-videos.py` — main script.
- `requirements.txt` — Python dependencies (install into a venv).
- `credentials.json` — Google API client credentials (you must create/download and place here).
- `token.json` — OAuth token created after first OAuth flow (automatically refreshed/overwritten).

## Environment variables (.env)
You can place values in a `.env` file (or set them in your environment). Defaults are provided in the script.
- `OPENAI_API_KEY` (required) — API key used by the OpenAI client.
- `VIDEO_OUTPUT_DIR` (optional) — default: `downloaded_videos`
- `TRANSCRIPTS_DIR` (optional) — default: `transcripts`
- `EXCEL_FILENAME` (optional) — default: `transcripts.xlsx`
- `EXCEL_FILE_PATH` (optional) — full path to the Excel file. If not set, the script builds from `TRANSCRIPTS_DIR` + `EXCEL_FILENAME`.

Example `.env`:

```text
OPENAI_API_KEY=sk-...
VIDEO_OUTPUT_DIR=downloaded_videos
TRANSCRIPTS_DIR=transcripts
EXCEL_FILENAME=transcripts.xlsx
# or use EXCEL_FILE_PATH to fully override
# EXCEL_FILE_PATH=transcripts/transcripts.xlsx
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
Single URL (interactive prompt):

```powershell
python .\transcribe-videos.py
# then paste the URL at the prompt
```

Single URL (non-interactive):

```powershell
python .\transcribe-videos.py --url "https://www.tiktok.com/...?"
```

Batch mode from `urls.txt` (one URL per line):

```powershell
python .\transcribe-videos.py --urls-file urls.txt
```

The script will:
- download each video into `VIDEO_OUTPUT_DIR`;
- convert audio and transcribe;
- append a row to the Excel workbook at `EXCEL_FILE_PATH` (created if missing);
- upload the final workbook to Google Drive.

## Thumbnail uploader

A companion script `upload-thumbnails-to-google.py` uploads images from the thumbnails folder to a specified Google Drive folder and tracks uploads in `state-thumbnails.json`.

Usage:

```powershell
python .\upload-thumbnails-to-google.py
```

You may set `THUMBNAILS_DIR`, `THUMBNAILS_STATE_FILE`, and `THUMBNAILS_DRIVE_FOLDER_ID` in `.env` to customize behavior.

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
- If you get an `InvalidFileException`, follow the README section above or remove/rename the bad Excel file so the script can recreate it.
- If `OPENAI_API_KEY` is not set the script will abort — set it in `.env` or your environment.
- If Google upload fails, check `credentials.json` and ensure you completed OAuth to produce `token.json`.
- Missing Python packages will show import errors; install required packages into the virtualenv.

## Optional improvements
- Add `--no-upload` to skip Google Drive upload.
- Add parallel processing (careful with memory/GPUs).
- Persist logs for debugging.

## License
No license specified — treat this repository as private/internal unless you add a license file.


