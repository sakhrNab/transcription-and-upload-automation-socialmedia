# System Overview - Quick Reference

## 🎯 What This System Does

```
INPUT: Video URLs (Instagram, TikTok, etc.)
   ↓
PROCESS: Download → Transcribe → Generate Thumbnails → Upload
   ↓
OUTPUT: Videos in Google Drive + AIWaverider + Tracking Sheets
```

## 🔄 Three Main Workflows

### 1. **Main Processing** (`python main.py`)
```
URLs File → Download Videos → Transcribe Audio → Upload to Both Drives → Update Sheets
```

### 2. **Continuous Scanner** (`python continuous_scanner.py`)
```
Watch Folder → Detect New Videos → Upload if Needed → Update Database
```

### 3. **Manual Upload** (Place videos in `finished_videos/`)
```
Manual Edit → Place in Folder → Scanner Detects → Uploads Automatically
```

## 📊 System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   INPUT         │    │   PROCESSING    │    │   OUTPUT        │
│                 │    │                 │    │                 │
│ • URLs File     │    │ • Video Download│    │ • Google Drive  │
│ • Manual Videos │    │ • Transcription │    │ • AIWaverider   │
│ • API Calls     │    │ • Thumbnails    │    │ • Google Sheets │
│                 │    │ • Uploads       │    │ • Local Backups │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🗄️ Database Structure

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ video_transcripts│    │ upload_tracking │    │ processing_queue│
│                 │    │                 │    │                 │
│ • Downloads     │    │ • Upload Status │    │ • Background    │
│ • Transcripts   │    │ • File Hashes   │    │   Tasks         │
│ • Metadata      │    │ • Platform IDs  │    │ • Worker Queue  │
│ • Status        │    │ • Error Logs    │    │ • Retry Logic   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 File Organization

```
assets/
├── downloads/           # Processing files
│   ├── videos/         # Downloaded videos
│   ├── audio/          # Converted audio
│   ├── thumbnails/     # Generated thumbnails
│   └── transcripts/    # Text transcripts
└── finished_videos/    # Manual uploads (scanner watches this)
```

## ⚡ Key Features

- **GPU Acceleration**: CUDA support for fast transcription
- **Dual Upload**: Google Drive + AIWaverider simultaneously
- **Real-time Monitoring**: Continuous file system watching
- **Smart Tracking**: Comprehensive database and sheets
- **Error Recovery**: Automatic retries and fallbacks
- **Local Backups**: CSV, JSON, Excel file backups

## 🚀 Quick Commands

```bash
# Process URLs from file
python main.py --urls-file data/urls.txt

# Start continuous scanner
python continuous_scanner.py

# Check system status
python -c "from system.health_metrics import metrics_collector; print(metrics_collector.get_health_status())"
```

## 📈 Performance

- **Transcription**: 30-120s per video (GPU), 2-5min (CPU)
- **Upload**: 10-60s per video
- **Throughput**: 10-50 videos per hour (depending on size)
- **Memory**: 2-4GB typical, 6-8GB with large models

## 🔧 Configuration

All settings in `.env` file:
- Google API credentials
- AIWaverider token
- OpenAI API key (for smart naming)
- Processing parameters
- Database settings

## 📊 Monitoring

- **Logs**: `logs/` directory
- **Sheets**: Real-time Google Sheets updates
- **Health**: Built-in metrics and status tracking
- **Backups**: Automatic local file backups
