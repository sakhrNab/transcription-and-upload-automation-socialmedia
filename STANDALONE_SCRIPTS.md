# 🚀 Standalone Scripts Documentation

This document describes all the standalone scripts you can run independently from the main application.

## 📥 Download & Processing Scripts

### 1. `download_only.py` - Download Videos Only
**Purpose:** Downloads videos, extracts metadata, generates thumbnails, and updates database/sheets WITHOUT transcription or uploads.

```bash
# Basic usage - scans assets/finished_videos/
python download_only.py

# Download specific videos
python download_only.py --videos "video1.mp4" "video2.mp4"

# Download from specific folder
python download_only.py --folder "path/to/videos"

# Test mode (dry run)
python download_only.py --test
```

**What it does:**
- Downloads videos from URLs or files
- Extracts metadata (title, description, duration, etc.)
- Generates thumbnails
- Updates database and sheets
- **Skips transcription and uploads**

### 2. `download_videos.bat` - Windows Batch Wrapper
**Purpose:** Windows-friendly interface for download-only operations.

```bash
download_videos.bat
```

---

## 📤 Upload Scripts

### 3. `upload_only.py` - Upload Videos Only
**Purpose:** Uploads videos from `assets/finished_videos/` to Google Drive and AIWaverider, updates sheets and database.

```bash
# Basic usage - scans assets/finished_videos/
python upload_only.py

# Upload specific videos
python upload_only.py --videos "video1.mp4" "video2.mp4"

# Upload from specific folder
python upload_only.py --folder "path/to/videos"

# Test mode (dry run)
python upload_only.py --test
```

**What it does:**
- Uploads videos to Google Drive
- Uploads videos to AIWaverider
- Updates master tracking sheet
- Updates transcripts sheet
- Updates database with upload status
- **Skips download and transcription**

### 4. `upload_videos.bat` - Windows Batch Wrapper
**Purpose:** Windows-friendly interface for upload-only operations.

```bash
upload_videos.bat
```

### 5. `upload_specific.py` - Advanced Upload Options
**Purpose:** Upload videos with advanced filtering and selection options.

```bash
# Upload by status
python upload_specific.py --status PENDING

# Upload by filename pattern
python upload_specific.py --pattern "rick"

# Upload recent videos (last 24 hours)
python upload_specific.py --recent 24

# List all uploadable videos
python upload_specific.py --list

# Upload specific files
python upload_specific.py --videos "video1.mp4" "video2.mp4"
```

---

## 🔄 Background Services

### 6. `continuous_scanner.py` - Auto Upload Scanner
**Purpose:** Monitors `assets/finished_videos/` for new videos and automatically uploads them.

```bash
python continuous_scanner.py
```

**What it does:**
- Monitors `assets/finished_videos/` folder
- Automatically uploads new videos to Google Drive & AIWaverider
- Runs continuously in background
- Respects existing upload statuses
- **Press Ctrl+C to stop**

### 7. `start_scanner.bat` - Windows Scanner Launcher
**Purpose:** Windows-friendly interface for the continuous scanner.

```bash
start_scanner.bat
```

---

## 🛠️ Utility Scripts

### 8. `check_gpu.py` - GPU Detection
**Purpose:** Checks if your system has CUDA/GPU support for transcription.

```bash
python check_gpu.py
```

**What it shows:**
- PyTorch version and CUDA availability
- GPU device information
- Memory capabilities
- Whisper device test results

### 9. `update_video_metadata.py` - Metadata Extractor
**Purpose:** Extracts metadata from transcript file headers and updates the database.

```bash
python update_video_metadata.py
```

**What it does:**
- Scans `assets/transcripts/` folder
- Extracts metadata from transcript file headers
- Updates database with extracted information
- Useful for data recovery/migration

### 10. `test_scanner.py` - Scanner Testing
**Purpose:** Tests the continuous scanner functionality.

```bash
python test_scanner.py
```

**What it does:**
- Tests the continuous scanner functionality
- Creates test video files
- Verifies upload process
- Good for debugging scanner issues

---

## 📊 Main Application

### 11. `main.py` - Full Processing Pipeline
**Purpose:** Complete video processing pipeline (download → transcribe → upload → update sheets).

```bash
# Basic usage - processes URLs from urls.txt
python main.py

# Process specific URLs
python main.py "https://youtube.com/watch?v=abc123"

# Limited to 5 videos max (as configured)
```

---

## 🎯 Usage Scenarios

### Quick Downloads
```bash
# Download videos without processing
python download_only.py --max-videos 3
```

### Background Uploads
```bash
# Start auto-upload service
python continuous_scanner.py
```

### System Check
```bash
# Check GPU capabilities
python check_gpu.py
```

### Data Recovery
```bash
# Extract metadata from existing transcripts
python update_video_metadata.py
```

### Testing
```bash
# Test scanner functionality
python test_scanner.py
```

### Advanced Uploads
```bash
# Upload only pending videos
python upload_specific.py --status PENDING

# Upload videos with specific pattern
python upload_specific.py --pattern "rick"

# Upload recent videos
python upload_specific.py --recent 12
```

---

## 💡 Pro Tips

1. **Use `download_only.py`** when you want to download videos but process them manually later
2. **Use `upload_only.py`** when you have videos ready to upload
3. **Use `continuous_scanner.py`** for automated uploads of manually edited videos
4. **Use `upload_specific.py`** for advanced upload filtering and selection
5. **Use `check_gpu.py`** to optimize your transcription settings
6. **Use `update_video_metadata.py`** to recover metadata from existing transcript files
7. **Use `main.py`** for the complete automated pipeline

## 🔧 Requirements

All scripts require:
- Python 3.8+
- Virtual environment activated (`.venv`)
- Required packages installed (`pip install -r requirements.txt`)
- Google API credentials configured
- Database initialized

## 🚨 Important Notes

- All scripts are **independent** and can be run without affecting each other
- Scripts respect existing database records and won't duplicate work
- Use `--test` flag when available to see what would happen without making changes
- Always check the output for any errors or warnings
- Press `Ctrl+C` to stop long-running processes

---

**Happy processing! 🎉**
