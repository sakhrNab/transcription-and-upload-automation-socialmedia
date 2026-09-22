-- New Database Schema - Separated Concerns
-- This separates download/transcript tracking from upload tracking

-- Video Transcripts Table - Tracks downloads and transcripts
CREATE TABLE IF NOT EXISTS video_transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    url TEXT,
    title TEXT,
    description TEXT,
    username TEXT,
    uploader_id TEXT,
    channel_id TEXT,
    channel_url TEXT,
    platform TEXT,
    duration INTEGER,
    width INTEGER,
    height INTEGER,
    fps REAL,
    format_id TEXT,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    upload_date TEXT,
    thumbnail_url TEXT,
    webpage_url TEXT,
    extractor TEXT,
    transcription_text TEXT,
    transcription_status TEXT DEFAULT 'PENDING',
    smart_name TEXT,
    transcript_file_path TEXT,
    audio_file_path TEXT,
    thumbnail_file_path TEXT,
    video_file_size_mb REAL,
    transcript_word_count INTEGER,
    processing_time_seconds REAL,
    notes TEXT,
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upload Tracking Table - Tracks uploads to Google Drive and AIWaverider
CREATE TABLE IF NOT EXISTS upload_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'video' or 'thumbnail'
    file_hash TEXT,
    
    -- Google Drive tracking
    gdrive_id TEXT,
    gdrive_url TEXT,
    gdrive_upload_status TEXT DEFAULT 'PENDING',
    gdrive_upload_date TIMESTAMP,
    gdrive_folder_id TEXT,
    
    -- AIWaverider Drive tracking
    aiwaverider_id TEXT,
    aiwaverider_url TEXT,
    aiwaverider_upload_status TEXT DEFAULT 'PENDING',
    aiwaverider_upload_date TIMESTAMP,
    aiwaverider_folder_path TEXT,
    
    -- General tracking
    upload_attempts INTEGER DEFAULT 0,
    last_upload_attempt TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(video_id, file_type)
);

-- Processing Queue Table - For background task processing
CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    task_data TEXT NOT NULL, -- JSON data
    status TEXT DEFAULT 'PENDING',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_video_transcripts_video_id ON video_transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_video_transcripts_filename ON video_transcripts(filename);
CREATE INDEX IF NOT EXISTS idx_video_transcripts_transcription_status ON video_transcripts(transcription_status);
CREATE INDEX IF NOT EXISTS idx_video_transcripts_platform ON video_transcripts(platform);

CREATE INDEX IF NOT EXISTS idx_upload_tracking_video_id ON upload_tracking(video_id);
CREATE INDEX IF NOT EXISTS idx_upload_tracking_filename ON upload_tracking(filename);
CREATE INDEX IF NOT EXISTS idx_upload_tracking_file_type ON upload_tracking(file_type);
CREATE INDEX IF NOT EXISTS idx_upload_tracking_gdrive_status ON upload_tracking(gdrive_upload_status);
CREATE INDEX IF NOT EXISTS idx_upload_tracking_aiwaverider_status ON upload_tracking(aiwaverider_upload_status);
