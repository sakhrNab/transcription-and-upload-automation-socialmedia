# Social Media Content Processor & Tracker (Modular Architecture)

A comprehensive Python utility that orchestrates the entire social media content workflow using a modern modular architecture. Downloads videos (TikTok/Instagram/etc.) via yt-dlp, converts to audio, transcribes using Whisper with GPU acceleration, generates thumbnails, uploads to both Google Drive and AIWaverider Drive, maintains comprehensive tracking sheets, and includes a continuous scanner for automatic uploads.

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
- **`sheets_processor.py`** - Google Sheets integration (master tracking)
- **`transcripts_sheets_processor.py`** - Video transcripts Google Sheets

## 🔄 Complete System Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SOCIAL MEDIA CONTENT PROCESSOR                        │
│                              MODULAR ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MAIN ENTRY    │    │   CONTINUOUS    │    │   MANUAL UPLOAD │
│   POINT         │    │   SCANNER       │    │   PROCESSING    │
│   (main.py)     │    │   (continuous_  │    │   (main.py)     │
│                 │    │   scanner.py)   │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (core/orchestrator.py)                   │
│  • Coordinates all processors                                                  │
│  • Manages database connections                                                │
│  • Handles error recovery and retries                                          │
│  • Tracks processing metrics                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PROCESSING PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   VIDEO         │    │   THUMBNAIL     │    │   UPLOAD        │
│   PROCESSOR     │    │   PROCESSOR     │    │   PROCESSOR     │
│                 │    │                 │    │                 │
│ 1. Download     │    │ 1. Extract      │    │ 1. Google       │
│    videos       │    │    thumbnails   │    │    Drive        │
│ 2. Convert to   │    │ 2. Generate     │    │ 2. AIWaverider  │
│    audio        │    │    smart names  │    │    Drive        │
│ 3. Transcribe   │    │ 3. Optimize     │    │ 3. Update       │
│    with Whisper │    │    images       │    │    database     │
│ 4. Save         │    │ 4. Upload to    │    │ 4. Track        │
│    transcripts  │    │    both drives  │    │    status       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE LAYER                                       │
│  • video_transcripts table - Tracks downloads and transcripts                   │
│  • upload_tracking table - Tracks upload status to both platforms              │
│  • processing_queue table - Background task management                         │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            GOOGLE SHEETS INTEGRATION                            │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MASTER        │    │   VIDEO         │    │   LOCAL         │
│   TRACKING      │    │   TRANSCRIPTS   │    │   BACKUP        │
│   SHEET         │    │   SHEET         │    │   SYSTEM        │
│                 │    │                 │    │                 │
│ • All content   │    │ • Video         │    │ • CSV files     │
│   status        │    │   transcripts   │    │ • JSON files    │
│ • Thumbnails    │    │ • Metadata      │    │ • Excel files   │
│ • Upload        │    │ • 31 columns    │    │ • Automatic     │
│   status        │    │ • Smart names   │    │   backups       │
│ • Real-time     │    │ • Word counts   │    │ • Version       │
│   updates       │    │ • Status        │    │   control       │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ASSET ORGANIZATION                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

assets/
├── downloads/
│   ├── videos/           # Downloaded video files
│   ├── audio/            # Converted audio files (WAV)
│   ├── thumbnails/       # Generated thumbnails
│   ├── transcripts/      # Text transcripts
│   └── socialmedia/
│       ├── tracking/     # Local backup files
│       └── transcripts/  # Transcript backups
└── finished_videos/      # Manually edited videos (continuous scanner watches this)

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            WORKFLOW SCENARIOS                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

SCENARIO 1: MAIN PROCESSING (python main.py)
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Read URLs   │───▶│ Download    │───▶│ Transcribe  │───▶│ Upload to   │
│ from file   │    │ Videos      │    │ Audio       │    │ Both Drives │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Validate    │    │ Extract     │    │ Generate    │    │ Update      │
│ URLs        │    │ Metadata    │    │ Thumbnails  │    │ Sheets      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

SCENARIO 2: CONTINUOUS SCANNER (python continuous_scanner.py)
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Watch       │───▶│ Detect      │───▶│ Check       │───▶│ Upload      │
│ Directory   │    │ New Files   │    │ Upload      │    │ if Needed   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ File        │    │ Generate    │    │ Update      │    │ Notify      │
│ System      │    │ Thumbnails  │    │ Database    │    │ Success     │
│ Events      │    │ if Needed   │    │ Status      │    │ / Failure   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

SCENARIO 3: MANUAL UPLOAD PROCESSING
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Place       │───▶│ Scanner     │───▶│ Process     │───▶│ Upload to   │
│ Videos in   │    │ Detects     │    │ Videos      │    │ Both Drives │
│ finished_   │    │ Changes     │    │ (if needed) │    │             │
│ videos/     │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## ✨ Features

### Core Processing
- Download video from a URL using `yt_dlp`
- Convert video to WAV using `ffmpeg`
- **GPU-accelerated transcription** using Whisper with CUDA support
- Generate thumbnails automatically
- Batch-mode: read multiple URLs from a text file (`--urls-file`)

### Dual Upload System
- **Google Drive**: Upload videos, thumbnails, transcripts, and tracking data
- **AIWaverider Drive**: Upload videos to `/videos/instagram/ai.uprise/` and thumbnails to `/thumbnails/instagram/`

### Comprehensive Tracking System
- **SQLite Database**: Robust state management with comprehensive metadata
- **Master Tracking Sheet**: Real-time Google Sheet with all content status and thumbnails
- **Video Transcripts Sheet**: Dedicated Google Sheet for video transcripts with 31 columns
- **Local Backup**: Automatic local backup to `assets/downloads/socialmedia/`
- **Smart Updates**: Updates existing entries, appends new ones (never overwrites existing data)
- **Duplicate Prevention**: Smart file checking to avoid re-uploads

### Continuous Scanner Service
- **Real-time Monitoring**: Watches `assets/finished_videos/` for new videos
- **Automatic Uploads**: Uploads videos when manually moved to finished folder
- **State Persistence**: Remembers processed files across restarts
- **Background Operation**: Runs continuously without manual intervention

### Advanced Features
- **GPU Acceleration**: CUDA support for faster transcription
- **Parallel Processing**: Concurrent video processing with configurable limits
- **Error Recovery**: Automatic retries with exponential backoff
- **Circuit Breaker**: Prevents cascading failures
- **Health Monitoring**: Comprehensive metrics and status tracking
- **Queue System**: Background task processing with workers
- **Smart Naming**: AI-powered video name generation
- **Metadata Extraction**: Comprehensive video metadata collection
- **Download-Only Mode**: Separate script for downloading without transcription
- **Video Limits**: Main processing limited to 5 videos max for efficiency
- **Flexible Processing**: Choose between full processing or download-only

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- CUDA-compatible GPU (optional, for faster transcription)
- Google API credentials
- AIWaverider API token

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd Transcripe-autoDetect-Video-upload-to-gDrive

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Basic Usage

#### 1. Main Processing (Download & Transcribe) - **Limited to 5 videos max**
```bash
# Process URLs from file (max 5 videos)
python main.py --urls-file data/urls.txt

# Process single URL
python main.py --url "https://instagram.com/p/example"

# Process with custom settings
python main.py --urls-file data/urls.txt --whisper-model large --max-concurrent 2
```

#### 2. Download-Only Mode (No Transcription, No Uploads)
```bash
# Download videos, metadata, and thumbnails only
python download_only.py --urls-file data/urls.txt

# Download with custom limit
python download_only.py --urls-file data/urls.txt --max-videos 10

# Download specific URLs
python download_only.py --urls "https://instagram.com/p/example1" "https://instagram.com/p/example2"

# Or use the batch file (Windows)
download_videos.bat
```

#### 3. Continuous Scanner (Background Monitoring)
```bash
# Start continuous scanner
python continuous_scanner.py

# Or use the batch file (Windows)
start_scanner.bat
```

#### 4. Manual Upload Processing
1. Place edited videos in `assets/finished_videos/`
2. The continuous scanner will automatically detect and upload them
3. Check the logs for upload status

## 📁 Project Structure

```
Transcripe-autoDetect-Video-upload-to-gDrive/
├── main.py                          # Main entry point (5 videos max)
├── download_only.py                 # Download-only script (unlimited videos)
├── continuous_scanner.py            # Continuous file monitoring service
├── start_scanner.bat               # Windows batch file to start scanner
├── download_videos.bat             # Windows batch file for download-only mode
├── test_scanner.py                 # Scanner testing utility
├── requirements.txt                # Python dependencies
├── .env                           # Environment variables (create this)
├── config/
│   ├── credentials.json           # Google API credentials
│   └── token.json                 # Google API token
├── core/
│   ├── orchestrator.py            # Main processing coordinator
│   └── processors/
│       ├── video_processor.py     # Video download & transcription
│       ├── upload_processor.py    # Google Drive uploads
│       ├── thumbnail_processor.py # Thumbnail generation
│       ├── aiwaverider_processor.py # AIWaverider Drive uploads
│       ├── sheets_processor.py    # Master tracking sheet
│       └── transcripts_sheets_processor.py # Video transcripts sheet
├── system/
│   ├── config.py                  # Configuration management
│   ├── new_database.py           # Database manager (new schema)
│   ├── database.py               # Legacy database manager
│   ├── queue_processor.py        # Background task processing
│   ├── health_metrics.py         # System monitoring
│   └── processor_logger.py       # Centralized logging
├── assets/
│   ├── downloads/
│   │   ├── videos/               # Downloaded video files
│   │   ├── audio/                # Converted audio files
│   │   ├── thumbnails/           # Generated thumbnails
│   │   ├── transcripts/          # Text transcripts
│   │   └── socialmedia/
│   │       ├── tracking/         # Local backup files
│   │       └── transcripts/      # Transcript backups
│   └── finished_videos/          # Manually edited videos (scanner watches this)
├── data/
│   ├── urls.txt                  # Input URLs file
│   └── cache/                    # Caching system
├── docs/
│   ├── README.md                 # Main documentation
│   ├── SYSTEM_OVERVIEW.md        # Quick reference guide
│   └── WORKFLOW_DIAGRAM.md       # Visual workflow diagrams
└── logs/                         # Log files
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Google API Configuration
GOOGLE_CREDENTIALS_FILE=config/credentials.json
GOOGLE_TOKEN_FILE=config/token.json
MASTER_SHEET_ID=your_master_sheet_id
MASTER_SHEET_NAME=socialmedia_tracker

# Video Transcripts Sheet
VIDEO_TRANSCRIPTS_ID=your_transcripts_sheet_id
VIDEO_TRANSCRIPTS_NAME=video_transcripts

# AIWaverider Configuration
AIWAVERIDER_TOKEN=your_aiwaverider_token
AIWAVERIDER_UPLOAD_URL=https://drive-backend.aiwaverider.com/webhook/files/upload

# OpenAI Configuration (for smart naming)
OPENAI_API_KEY=your_openai_api_key

# Processing Configuration
WHISPER_MODEL=base
MAX_AUDIO_DURATION=1800
CHUNK_DURATION=30
KEEP_AUDIO_FILES=true
MAX_CONCURRENT_VIDEOS=0
MAX_CONCURRENT_UPLOADS=3
```

### Database Schema

#### Video Transcripts Table
Tracks video downloads, metadata, and transcription status:
- `video_id` - Unique video identifier
- `filename` - Video filename
- `file_path` - Local file path
- `url` - Source URL
- `title`, `description` - Video metadata
- `username`, `uploader_id` - Creator information
- `platform` - Source platform (Instagram, TikTok, etc.)
- `duration`, `width`, `height`, `fps` - Video properties
- `view_count`, `like_count`, `comment_count` - Engagement metrics
- `transcription_text` - Whisper transcription result
- `transcription_status` - PENDING/COMPLETED/FAILED
- `smart_name` - AI-generated video name
- `created_at`, `updated_at` - Timestamps

#### Upload Tracking Table
Tracks upload status for videos and thumbnails:
- `video_id` - Links to video_transcripts table
- `filename` - Original filename
- `file_type` - 'video' or 'thumbnail'
- `file_hash` - Content hash for duplicate detection
- `gdrive_id`, `gdrive_url` - Google Drive information
- `gdrive_upload_status` - Upload status
- `aiwaverider_id`, `aiwaverider_url` - AIWaverider information
- `aiwaverider_upload_status` - Upload status
- `upload_attempts` - Retry counter
- `error_message` - Error details if failed

## 🎯 Usage Scenarios

### Scenario 1: Batch Video Processing
1. Add URLs to `data/urls.txt`
2. Run `python main.py --urls-file data/urls.txt`
3. System downloads, transcribes, and uploads all videos
4. Check Google Sheets for results

### Scenario 2: Continuous Monitoring
1. Run `python continuous_scanner.py`
2. Manually edit videos and place in `assets/finished_videos/`
3. Scanner automatically detects and uploads new videos
4. System updates database and sheets in real-time

### Scenario 3: Manual Upload Only
1. Place pre-edited videos in `assets/finished_videos/`
2. Run `python continuous_scanner.py`
3. System uploads videos without re-processing
4. Updates tracking sheets with upload status

## 🔍 Monitoring & Logs

### Log Files
- `logs/processor.log` - Main processing logs
- `logs/continuous_scanner.log` - Scanner-specific logs
- `logs/error.log` - Error tracking

### Health Metrics
- Processing duration and throughput
- Success/failure rates
- GPU memory usage
- Queue status and worker health
- Database connection status

### Google Sheets Monitoring
- **Master Tracking Sheet**: Real-time status of all content
- **Video Transcripts Sheet**: Comprehensive transcript database
- **Local Backups**: CSV, JSON, and Excel backups

## 🛠️ Advanced Features

### GPU Acceleration
- Automatic CUDA detection
- Memory management and cleanup
- Fallback to CPU if GPU unavailable
- Parallel processing optimization

### Error Recovery
- Exponential backoff retry logic
- Circuit breaker pattern
- Graceful degradation
- Comprehensive error logging

### Performance Optimization
- Configurable concurrency limits
- Smart caching system
- Database connection pooling
- Memory-efficient processing

### Security & Reliability
- API key management
- Secure credential storage
- Data validation and sanitization
- Backup and recovery systems

## 🚨 Troubleshooting

### Common Issues

#### 1. Transcription Empty Results
- **Cause**: Video has no speech content or very low audio quality
- **Solution**: This is normal behavior for music-only or silent videos
- **Check**: Audio file size and quality in `assets/downloads/audio/`

#### 2. GPU Memory Issues
- **Cause**: Large models or insufficient GPU memory
- **Solution**: Use smaller Whisper model (`base` instead of `large`)
- **Check**: GPU memory usage in logs

#### 3. Upload Failures
- **Cause**: Network issues or API rate limits
- **Solution**: System automatically retries with exponential backoff
- **Check**: Upload status in Google Sheets

#### 4. Database Connection Issues
- **Cause**: Database file corruption or permission issues
- **Solution**: Check database file permissions and integrity
- **Check**: Database logs and connection status

### Debug Mode
```bash
# Enable verbose logging
python main.py --urls-file data/urls.txt --verbose

# Check system status
python -c "from system.health_metrics import metrics_collector; print(metrics_collector.get_health_status())"
```

## 📊 Performance Metrics

### Typical Performance
- **Video Download**: 10-30 seconds per video
- **Audio Conversion**: 5-15 seconds per video
- **Transcription**: 30-120 seconds per video (GPU), 2-5 minutes (CPU)
- **Thumbnail Generation**: 2-5 seconds per video
- **Upload**: 10-60 seconds per video (depending on size)

### Resource Usage
- **CPU**: Moderate during processing, low during monitoring
- **GPU**: High during transcription, idle otherwise
- **Memory**: 2-4GB typical, 6-8GB with large models
- **Storage**: ~100MB per video (video + audio + thumbnail + transcript)

## 🔄 Recent Updates

### What's New in Modular Architecture
- **Continuous Scanner**: Real-time file monitoring and automatic uploads
- **Dual Google Sheets**: Separate sheets for tracking and transcripts
- **Enhanced Database**: Separated concerns with video_transcripts and upload_tracking tables
- **Duplicate Prevention**: Smart file checking to avoid re-uploads
- **Improved File Structure**: Organized asset storage with clear separation
- **Better Error Handling**: Comprehensive error recovery and logging
- **GPU Optimization**: Enhanced CUDA support and memory management
- **Queue System**: Background task processing with worker management
- **Health Monitoring**: Real-time system status and metrics
- **Local Backups**: Automatic backup of all data in multiple formats
- **Download-Only Mode**: Separate script for downloading without transcription
- **Video Limits**: Main processing limited to 5 videos max for efficiency
- **Path Normalization**: Consistent file path handling across platforms
- **Clean Architecture**: Removed unnecessary test files and migration scripts

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Check the Google Sheets for processing status
4. Create an issue with detailed information

---

**Note**: This system is designed for content creators and social media managers who need to process large volumes of video content efficiently. The modular architecture ensures reliability, scalability, and maintainability.