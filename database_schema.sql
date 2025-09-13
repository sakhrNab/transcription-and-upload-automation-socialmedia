-- Database Schema for Social Media Processor
-- This file contains the SQL schema for creating the database from scratch
-- Run this to initialize a new database in any environment

-- Videos table
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Thumbnails table
CREATE TABLE IF NOT EXISTS thumbnails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    video_filename TEXT,
    drive_id TEXT,
    drive_url TEXT,
    upload_status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AIWaverider uploads table
CREATE TABLE IF NOT EXISTS aiwaverider_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    upload_status TEXT DEFAULT 'PENDING',
    upload_id TEXT,
    total_chunks INTEGER DEFAULT 0,
    uploaded_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing queue table
CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    task_data TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    priority INTEGER DEFAULT 1,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_unit TEXT,
    tags TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_videos_upload_status ON videos(upload_status);
CREATE INDEX IF NOT EXISTS idx_thumbnails_filename ON thumbnails(filename);
CREATE INDEX IF NOT EXISTS idx_aiwaverider_filename ON aiwaverider_uploads(filename);
CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
