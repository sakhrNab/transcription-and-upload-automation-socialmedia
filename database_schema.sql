-- Social Media Processor Database Schema
-- This file contains the complete database schema for the modular social media processor
-- The database is automatically initialized by the system, but this file can be used
-- for manual setup or understanding the schema structure.

-- Videos table - Main video content tracking
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    url TEXT,
    drive_id TEXT,
    drive_url TEXT,
    upload_status TEXT DEFAULT 'PENDING',
    transcription_status TEXT DEFAULT 'PENDING',
    transcription_text TEXT,
    smart_name TEXT,
    aiwaverider_status TEXT DEFAULT 'PENDING',
    file_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Video metadata
    video_id TEXT,
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
    extractor TEXT
);

-- Thumbnails table - Thumbnail image tracking
CREATE TABLE IF NOT EXISTS thumbnails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    video_filename TEXT,
    drive_id TEXT,
    drive_url TEXT,
    upload_status TEXT DEFAULT 'PENDING',
    aiwaverider_status TEXT DEFAULT 'PENDING',
    file_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_upload_status ON videos(upload_status);
CREATE INDEX IF NOT EXISTS idx_videos_transcription_status ON videos(transcription_status);
CREATE INDEX IF NOT EXISTS idx_videos_aiwaverider_status ON videos(aiwaverider_status);

CREATE INDEX IF NOT EXISTS idx_thumbnails_filename ON thumbnails(filename);
CREATE INDEX IF NOT EXISTS idx_thumbnails_video_filename ON thumbnails(video_filename);
CREATE INDEX IF NOT EXISTS idx_thumbnails_upload_status ON thumbnails(upload_status);
CREATE INDEX IF NOT EXISTS idx_thumbnails_aiwaverider_status ON thumbnails(aiwaverider_status);

-- Sample data (optional - for testing)
-- INSERT INTO videos (filename, file_path, video_id, title, platform) 
-- VALUES ('sample_video.mp4', 'assets/downloads/videos/sample_video.mp4', 'sample123', 'Sample Video', 'Instagram');

-- INSERT INTO thumbnails (filename, file_path, video_filename) 
-- VALUES ('sample_thumbnail.jpg', 'assets/downloads/thumbnails/sample_thumbnail.jpg', 'sample_video.mp4');
