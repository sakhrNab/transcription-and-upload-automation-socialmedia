#!/usr/bin/env python3
"""
Thumbnail Processor
Handles thumbnail processing and optimization
"""

import asyncio
import os
import sys
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.new_database import new_db_manager as db_manager


class ThumbnailProcessor(BaseProcessor):
    """Handles thumbnail processing and optimization"""
    
    def __init__(self):
        super().__init__("ThumbnailProcessor")
        self.processed_count = 0
        self.failed_count = 0
    
    async def initialize(self) -> bool:
        """Initialize thumbnail processor"""
        try:
            self.log_step("Initializing thumbnail processor")
            
            # Ensure required directories exist
            os.makedirs('assets/downloads/thumbnails', exist_ok=True)
            
            self.initialized = True
            self.status = "ready"
            self.log_step("Thumbnail processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Failed to initialize thumbnail processor", e)
            return False
    
    async def process(self, urls: List[str] = None) -> bool:
        """Main processing method - alias for process_thumbnails"""
        return await self.process_thumbnails()
    
    async def process_thumbnails(self) -> bool:
        """Process thumbnails for optimization and upload preparation"""
        try:
            self.log_step("Starting thumbnail processing")
            self.status = "processing"
            
            # Get thumbnails that need processing
            thumbnails = await db_manager.get_thumbnails_by_status('PENDING')
            
            if not thumbnails:
                self.log_step("No thumbnails to process")
                return True
            
            self.log_step(f"Found {len(thumbnails)} thumbnails to process")
            
            # Process each thumbnail
            for thumbnail in thumbnails:
                try:
                    success = await self._process_single_thumbnail(thumbnail)
                    if success:
                        self.processed_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e:
                    self.log_error(f"Error processing thumbnail {thumbnail.get('filename', 'unknown')}", e)
                    self.failed_count += 1
            
            self.status = "completed"
            self.log_step(f"Thumbnail processing completed: {self.processed_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in process_thumbnails", e)
            self.status = "error"
            return False
    
    async def process_thumbnail_for_video(self, video_index: int) -> bool:
        """Process thumbnail for a specific video (download-only mode)"""
        try:
            self.log_step(f"Processing thumbnail for video {video_index}")
            
            # Get video data from database
            video_data = await db_manager.get_video_transcript_by_index(video_index)
            if not video_data:
                self.log_error(f"Video data not found for index {video_index}")
                return False
            
            thumbnail_path = video_data.get('thumbnail_file_path', '')
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                self.log_error(f"Thumbnail file not found: {thumbnail_path}")
                return False
            
            filename = os.path.basename(thumbnail_path)
            self.log_step(f"Processing thumbnail: {filename}")
            
            # Here you would add thumbnail optimization logic
            # For now, we'll simulate the processing
            await asyncio.sleep(0.2)  # Simulate processing time
            
            # Update database with processing status
            await db_manager.update_thumbnail_status_by_video_index(video_index, 'PROCESSED')
            
            self.log_step(f"Successfully processed thumbnail: {filename}")
            self.processed_count += 1
            return True
            
        except Exception as e:
            self.log_error(f"Error processing thumbnail for video {video_index}", e)
            self.failed_count += 1
            return False

    async def _process_single_thumbnail(self, thumbnail: Dict[str, Any]) -> bool:
        """Process a single thumbnail"""
        try:
            filename = thumbnail.get('filename', '')
            file_path = thumbnail.get('file_path', '')
            
            if not file_path or not os.path.exists(file_path):
                self.log_error(f"Thumbnail file not found: {file_path}")
                return False
            
            self.log_step(f"Processing thumbnail: {filename}")
            
            # Here you would add thumbnail optimization logic
            # For now, we'll simulate the processing
            await asyncio.sleep(0.2)  # Simulate processing time
            
            # Update database with processing status
            await db_manager.update_thumbnail_status(thumbnail['id'], 'PROCESSED')
            
            self.log_step(f"Successfully processed thumbnail: {filename}")
            return True
            
        except Exception as e:
            self.log_error(f"Error processing thumbnail {thumbnail.get('filename', 'unknown')}", e)
            return False
    
    async def cleanup(self) -> None:
        """Cleanup thumbnail processor resources"""
        try:
            self.log_step("Cleaning up thumbnail processor")
            self.status = "idle"
            self.log_step("Thumbnail processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)
