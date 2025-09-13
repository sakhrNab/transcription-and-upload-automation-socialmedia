# Social Media Content Processor & Tracker (Modular Architecture)

A comprehensive Python utility that orchestrates the entire social media content workflow using a modern modular architecture. Downloads videos (TikTok/Instagram/etc.) via yt-dlp, converts to audio, transcribes using Whisper with GPU acceleration, generates thumbnails, uploads to both Google Drive and AIWaverider Drive, and maintains a master tracking sheet with real-time status updates.

## 🏗️ Architecture Overview

### Modular Design
- **`main.py`** - Entry point and command-line interface
- **`core/orchestrator.py`** - Main coordinator that manages the processing pipeline
- **`core/processors/`** - Individual processors for each task
- **`system/`** - Database, configuration, and utility modules
- **`assets/`** - Organized asset storage structure

### Core Processors
- **`video_processor.py`** - Video download, conversion, and transcription
- **`upload_processor.py`** - Google Drive video uploads
- **`thumbnail_processor.py`** - Thumbnail generation and processing
- **`aiwaverider_processor.py`** - AIWaverider Drive uploads
- **`sheets_processor.py`** - Google Sheets integration
- **`excel_processor.py`** - Excel file generation and upload

## ✨ Features

### Core Processing
- Download video from a URL using `yt_dlp`
- Convert video to WAV using `ffmpeg`
- **GPU-accelerated transcription** using Whisper with CUDA support
- Generate thumbnails automatically
- Batch-mode: read multiple URLs from a text file (`--urls-file`)

### Dual Upload System
- **Google Drive**: Upload videos, thumbnails, and Excel workbooks
- **AIWaverider Drive**: Upload videos to `/videos/instagram/ai.uprise/` and thumbnails to `/thumbnails/instagram/`

### Master Tracking System
- **SQLite Database**: Robust state management with comprehensive metadata
- **Google Sheets Integration**: Real-time tracking sheet with all content status
- **Local Backup**: Automatic local backup to `assets/downloads/socialmedia/tracking/`
- **Smart Updates**: Updates existing entries, appends new ones (never overwrites existing data)
- **Thumbnail Display**: Actual thumbnail images displayed in the tracking sheet

### Advanced Features
- **GPU Acceleration**: CUDA support for faster transcription
- **Comprehensive Metadata**: 30+ data fields including FPS, format, engagement metrics
- **Error Recovery**: Robust error handling with retry mechanisms
- **Duplicate Prevention**: Smart file checking to avoid re-uploads
- **Offline Mode**: Continues working even when Google services are unavailable

## 📁 Project Structure

```
📦 Social Media Processor
├── 🎯 main.py                          # Entry point
├── 📊 social_media.db                  # SQLite database
├── 📋 database_schema.sql              # Database schema (for manual setup)
├── ⚙️ requirements.txt                 # Dependencies
├── 🔧 check_gpu.py                     # GPU testing utility
├── 📝 update_video_metadata.py         # Metadata migration utility
├── 📁 core/                            # Core processing modules
│   ├── orchestrator.py                 # Main coordinator
│   └── processors/                     # Individual processors
│       ├── video_processor.py          # Video processing & transcription
│       ├── upload_processor.py         # Google Drive uploads
│       ├── thumbnail_processor.py      # Thumbnail processing
│       ├── aiwaverider_processor.py    # AIWaverider Drive uploads
│       ├── sheets_processor.py         # Google Sheets integration
│       └── excel_processor.py          # Excel generation
├── 📁 system/                          # System utilities
│   ├── database.py                     # SQLite database management
│   ├── config.py                       # Configuration management
│   ├── processor_logger.py             # Logging system
│   ├── error_recovery.py               # Error handling
│   ├── health_metrics.py               # System monitoring
│   └── queue_processor.py              # Queue management
├── 📁 assets/                          # Asset storage
│   └── downloads/                      # All downloaded content
│       ├── videos/                     # Video files
│       ├── audio/                      # Audio files
│       ├── thumbnails/                 # Thumbnail images
│       ├── transcripts/                # Transcription files
│       └── socialmedia/tracking/       # Local tracking data
└── 📁 config/                          # Configuration files
    └── token.json                      # Google API tokens
```

## 🚀 Quick Start

### 1. Installation
```powershell
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# For GPU acceleration (optional but recommended)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. Configuration
Create a `.env` file with your API keys:
```env
# Required API Keys
OPENAI_API_KEY=sk-proj-...
AIWAVERIDER_DRIVE_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
UPLOAD_FILE_AIWAVERIDER=https://drive-backend.aiwaverider.com/webhook/files/upload

# Google Services
MASTER_SHEET_ID=1HNKPIhq1kB1xoS52cM2U7KOdiJS8pqiQ7j_fbTQOUPI
GOOGLE_CREDENTIALS_FILE=config/credentials.json
GOOGLE_TOKEN_FILE=config/token.json
```

### 3. Database Setup
The database is automatically created on first run. For manual setup:
```sql
-- Use the provided database_schema.sql
sqlite3 social_media.db < database_schema.sql
```

### 4. Usage
```powershell
# Process URLs from file
python main.py --urls-file urls.txt

# Process single URL
python main.py --url "https://www.instagram.com/p/..."

# Check GPU status
python check_gpu.py
```

## 📊 Database Schema

### Videos Table
Comprehensive video tracking with 30+ metadata fields:
- **Basic Info**: filename, file_path, url, smart_name
- **Upload Status**: drive_id, drive_url, upload_status, aiwaverider_status
- **Transcription**: transcription_text, transcription_status
- **Metadata**: video_id, title, description, username, platform
- **Technical**: duration, width, height, fps, format_id
- **Engagement**: view_count, like_count, comment_count
- **Timestamps**: created_at, updated_at

### Thumbnails Table
Thumbnail image tracking:
- **File Info**: filename, file_path, video_filename
- **Upload Status**: drive_id, drive_url, upload_status, aiwaverider_status
- **Metadata**: file_hash, created_at, updated_at

## 🔧 Environment Variables

### Required API Keys
- `OPENAI_API_KEY` - OpenAI API key for GPT-4o-mini naming
- `AIWAVERIDER_DRIVE_TOKEN` - Bearer token for AIWaverider Drive API
- `UPLOAD_FILE_AIWAVERIDER` - AIWaverider upload endpoint URL

### Google Services
- `MASTER_SHEET_ID` - Google Sheets ID for master tracking
- `GOOGLE_CREDENTIALS_FILE` - Google API client credentials (default: `config/credentials.json`)
- `GOOGLE_TOKEN_FILE` - OAuth token file (default: `config/token.json`)

### Processing Configuration
- `WHISPER_MODEL` - Whisper model size (default: `base`)
- `MAX_AUDIO_DURATION` - Max audio duration in seconds (default: `1800`)
- `KEEP_AUDIO_FILES` - Keep audio files after processing (default: `true`)

## 🎯 Processing Pipeline

1. **Video Processing**: Download, convert to audio, transcribe with GPU acceleration
2. **Thumbnail Generation**: Extract and process thumbnail images
3. **Google Drive Upload**: Upload videos and thumbnails to Google Drive
4. **AIWaverider Upload**: Upload to AIWaverider Drive with duplicate checking
5. **Google Sheets Update**: Update master tracking sheet with real-time status
6. **Excel Generation**: Create comprehensive Excel workbook with all metadata
7. **Local Backup**: Save all data locally for offline access

## 🚀 Performance Features

### GPU Acceleration
- **CUDA Support**: Automatic GPU detection and usage
- **Fallback**: Graceful fallback to CPU if GPU unavailable
- **Memory Management**: Efficient GPU memory usage with cleanup

### Database Optimization
- **SQLite**: Fast, reliable local database
- **Indexes**: Optimized queries with proper indexing
- **Migration**: Automatic schema updates and migrations

### Upload Optimization
- **Duplicate Prevention**: Smart file checking before uploads
- **Chunked Uploads**: Large file support with chunked uploads
- **Parallel Processing**: Concurrent uploads where possible
- **Retry Logic**: Robust error handling with exponential backoff

## 🔍 Monitoring & Logging

### Comprehensive Logging
- **Structured Logs**: Detailed logging for all operations
- **Progress Tracking**: Real-time status updates
- **Error Reporting**: Detailed error messages with context
- **Performance Metrics**: Processing times and success rates

### Health Monitoring
- **System Metrics**: CPU, memory, disk usage
- **Queue Status**: Processing queue monitoring
- **Error Recovery**: Automatic retry mechanisms
- **Circuit Breakers**: Prevent cascading failures

## 🛠️ Troubleshooting

### Common Issues

#### GPU Issues
```powershell
# Check GPU status
python check_gpu.py

# Install CUDA-enabled PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### Database Issues
```powershell
# Recreate database
rm social_media.db
python main.py --urls-file urls.txt

# Manual database setup
sqlite3 social_media.db < database_schema.sql
```

#### Authentication Issues
- Ensure `config/credentials.json` is present
- Check `config/token.json` is valid
- Verify `MASTER_SHEET_ID` is correct

### Debug Mode
Enable detailed logging by setting `LOG_LEVEL=DEBUG` in `.env` file.

## 🔄 Migration from Old System

If migrating from the old monolithic system:

1. **Database Migration**: Run `python update_video_metadata.py` to migrate existing data
2. **File Structure**: Old `downloads/` directory is now `assets/downloads/`
3. **State Management**: JSON state files replaced with SQLite database
4. **Configuration**: Update `.env` file with new structure

## 📈 Advanced Features

### Excel Integration
- **30+ Columns**: Comprehensive metadata tracking
- **Data Validation**: Dropdown lists and data validation
- **Auto-upload**: Automatic upload to Google Drive
- **Backup**: Local backup before updates

### AIWaverider Drive Integration
- **Smart Uploads**: Duplicate prevention and file checking
- **Chunked Uploads**: Large file support
- **Caching**: Efficient file list caching
- **Error Recovery**: Robust retry mechanisms

### Google Sheets Integration
- **Real-time Updates**: Live status tracking
- **Thumbnail Display**: Actual images in sheets
- **Smart Updates**: Never overwrites existing data
- **Local Backup**: Offline data access

## 📝 License

No license specified — treat this repository as private/internal unless you add a license file.

---

## 🆕 What's New in Modular Architecture

### Improvements Over Old System
- **🏗️ Modular Design**: Clean separation of concerns
- **⚡ GPU Acceleration**: 3-5x faster transcription
- **📊 SQLite Database**: Robust state management
- **🔧 Better Error Handling**: Comprehensive error recovery
- **📈 Performance**: Optimized processing pipeline
- **🧹 Cleaner Code**: Maintainable and extensible
- **📚 Better Documentation**: Comprehensive guides and examples

### Migration Benefits
- **🚀 Faster Processing**: GPU acceleration and optimizations
- **💾 Better Data Management**: SQLite with comprehensive metadata
- **🔧 Easier Maintenance**: Modular architecture
- **📊 Enhanced Tracking**: 30+ data fields vs 25 in old system
- **🛡️ Better Reliability**: Robust error handling and recovery