#!/usr/bin/env python3
"""
Centralized Configuration Management
Uses Pydantic for validation and type safety
"""

from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    """Centralized configuration with validation"""
    
    # Google API Configuration
    google_credentials_file: str = Field(default="config/credentials.json", description="Google API credentials file")
    google_token_file: str = Field(default="config/token.json", description="Google API token file")
    master_sheet_id: str = Field(default="1HNKPIhq1kB1xoS52cM2U7KOdiJS8pqiQ7j_fbTQOUPI", description="Google Sheets ID for master tracking")
    master_sheet_name: str = Field(default="socialmedia_tracker", description="Google Sheets name")
    
    # Video Transcripts Sheet Configuration
    transcripts_sheet_id: str = Field(default="1vDHi5qGBrerPZ2LvMFY1IkyWoiCIWOD2_rW6u7_NQ1s", description="Google Sheets ID for video transcripts (auto-created if empty)")
    transcripts_sheet_name: str = Field(default="video_transcripts", description="Google Sheets name for video transcripts")
    
    # AIWaverider Configuration
    aiwaverider_token: str = Field(default="", description="AIWaverider API token")
    aiwaverider_upload_url: str = Field(
        default="https://drive-backend.aiwaverider.com/webhook/files/upload",
        description="AIWaverider upload endpoint"
    )
    
    # Legacy environment variable mappings
    aiwaverider_drive_token: str = Field(default="", description="Legacy AIWaverider token field")
    upload_file_aiwaverider: str = Field(default="", description="Legacy AIWaverider upload URL field")
    
    # Performance Configuration
    max_concurrent_uploads: int = Field(default=3, description="Maximum concurrent uploads")
    max_concurrent_videos: int = Field(default=0, description="Maximum concurrent video processing (0 = auto-detect)")
    cache_duration_hours: int = Field(default=1, description="Cache duration in hours")
    chunk_size_mb: int = Field(default=5, description="Chunk size for large file uploads in MB")
    upload_timeout_seconds: int = Field(default=300, description="Upload timeout in seconds")
    
    # Video Processing Configuration
    whisper_model: str = Field(default="base", description="Whisper model size")
    max_audio_duration: int = Field(default=1800, description="Maximum audio duration in seconds")
    chunk_duration: int = Field(default=30, description="Audio chunk duration in seconds")
    keep_audio_files: bool = Field(default=True, description="Keep audio files after processing")
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///social_media.db", description="Database URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    
    # Queue Configuration
    max_queue_size: int = Field(default=1000, description="Maximum queue size")
    worker_timeout_seconds: int = Field(default=3600, description="Worker timeout in seconds")
    
    # Error Recovery Configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_base_delay: float = Field(default=1.0, description="Base delay for exponential backoff")
    circuit_breaker_failure_threshold: int = Field(default=5, description="Circuit breaker failure threshold")
    circuit_breaker_timeout: int = Field(default=60, description="Circuit breaker timeout in seconds")
    
    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_retention_days: int = Field(default=30, description="Metrics retention period in days")
    
    # Webhook Configuration (optional)
    webhook_urls: List[str] = Field(default=[], description="Webhook URLs for notifications")
    
    # File Paths
    downloads_dir: str = Field(default="downloads", description="Downloads directory")
    finished_videos_dir: str = Field(default="finished_videos", description="Finished videos directory")
    thumbnails_dir: str = Field(default="downloads/thumbnails", description="Thumbnails directory")
    transcripts_dir: str = Field(default="transcripts", description="Transcripts directory")
    tracking_dir: str = Field(default="downloads/socialmedia/tracking", description="Tracking data directory")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
    
    @validator('master_sheet_id')
    def validate_sheet_id(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid Google Sheets ID")
        return v
    
    @validator('aiwaverider_token')
    def validate_token(cls, v):
        if v and len(v) < 10:
            raise ValueError("Invalid AIWaverider token")
        return v
    
    @validator('max_concurrent_uploads')
    def validate_concurrent_uploads(cls, v):
        if v < 1 or v > 10:
            raise ValueError("Max concurrent uploads must be between 1 and 10")
        return v
    
    @validator('chunk_size_mb')
    def validate_chunk_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Chunk size must be between 1 and 100 MB")
        return v
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Handle legacy environment variable mappings
        if not self.aiwaverider_token and self.aiwaverider_drive_token:
            self.aiwaverider_token = self.aiwaverider_drive_token
        if not self.aiwaverider_upload_url and self.upload_file_aiwaverider:
            self.aiwaverider_upload_url = self.upload_file_aiwaverider

# Global settings instance
settings = Settings()

# Environment-specific overrides
if os.getenv('ENVIRONMENT') == 'development':
    settings.cache_duration_hours = 0.1  # 6 minutes for development
    settings.max_concurrent_uploads = 2
elif os.getenv('ENVIRONMENT') == 'production':
    settings.cache_duration_hours = 24  # 24 hours for production
    settings.max_concurrent_uploads = 5
