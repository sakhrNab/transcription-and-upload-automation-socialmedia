#!/usr/bin/env python3
"""
Social Media Content Orchestrator
Coordinates all processing components in a unified pipeline
"""

import asyncio
import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.processor_logger import processor_logger as logger
from system.config import settings
from system.new_database import new_db_manager as db_manager
from system.queue_processor import queue_processor
from system.health_metrics import metrics_collector

# Import processors
from core.processors.video_processor import VideoProcessor
from core.processors.upload_processor import UploadProcessor
from core.processors.thumbnail_processor import ThumbnailProcessor
from core.processors.aiwaverider_processor import AIWaveriderProcessor
from core.processors.sheets_processor import SheetsProcessor
from core.processors.transcripts_sheets_processor import TranscriptsSheetsProcessor


class SocialMediaOrchestrator:
    """Main orchestrator that coordinates all processing components"""
    
    def __init__(self):
        """Initialize the orchestrator with all processors"""
        self.video_processor = VideoProcessor()
        self.upload_processor = UploadProcessor()
        self.thumbnail_processor = ThumbnailProcessor()
        self.aiwaverider_processor = AIWaveriderProcessor()
        self.sheets_processor = SheetsProcessor()
        self.transcripts_sheets_processor = TranscriptsSheetsProcessor()
        
        self.processing_pipeline = [
            self.video_processor,
            self.upload_processor,
            self.thumbnail_processor,
            self.aiwaverider_processor,
            self.sheets_processor,
            self.transcripts_sheets_processor
        ]
    
    async def initialize(self):
        """Initialize all processors"""
        try:
            logger.log_step("Initializing orchestrator components")
            
            # Initialize database
            await db_manager.initialize()
            logger.log_step("Database initialized")
            
            # Start metrics collection
            self.metrics = metrics_collector.start_processing_metrics()
            logger.log_step("Metrics collection started")
            
            # Start queue processor
            await queue_processor.start()
            logger.log_step("Queue processor started")
            
            # Initialize all processors
            for processor in self.processing_pipeline:
                await processor.initialize()
                if hasattr(processor, 'drive_folder'):
                    logger.log_step(f"Initialized {processor.__class__.__name__} with drive_folder: {processor.drive_folder}")
                else:
                    logger.log_step(f"Initialized {processor.__class__.__name__}")
            
            logger.log_step("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.log_error(f"Error initializing orchestrator: {str(e)}")
            return False
    
    async def process_urls(self, urls: List[str]) -> bool:
        """Process a list of URLs through the complete pipeline"""
        try:
            logger.log_step(f"Starting pipeline processing for {len(urls)} URLs")
            
            # Ensure database is initialized
            if not db_manager._initialized:
                await db_manager.initialize()
            
            # Step 1: Video Processing
            logger.log_step("Step 1: Video processing and transcription")
            video_results = await self.video_processor.process_urls(urls)
            if not video_results:
                logger.log_step("Video processing had issues, but continuing with uploads for completed videos")
            else:
                logger.log_step("Video processing completed successfully")
            
            # Update database and sheets after video processing
            logger.log_step("Updating database and sheets after video processing...")
            await self._update_database_and_sheets_after_step("video_processing")
            
            # Always continue with uploads regardless of video processing results
            logger.log_step("Continuing with upload processing for any successfully processed videos")
            
            # Step 2: Google Drive Upload Processing (parallel with thumbnails)
            logger.log_step("Step 2: Google Drive upload processing")
            upload_tasks = [
                self.upload_processor.process_videos(),
                self.upload_processor.process_thumbnails()
            ]
            
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Check for upload errors
            for i, result in enumerate(upload_results):
                if isinstance(result, Exception):
                    logger.log_error(f"Google Drive upload task {i} failed: {str(result)}")
                elif not result:
                    logger.log_error(f"Google Drive upload task {i} returned False")
            
            # Update database and sheets after Google Drive uploads
            logger.log_step("Updating database and sheets after Google Drive uploads...")
            await self._update_database_and_sheets_after_step("google_drive_upload")
            
            # Step 3: AIWaverider Upload (videos and thumbnails)
            logger.log_step("Step 3: AIWaverider Drive upload (videos and thumbnails)")
            aiwaverider_result = await self.aiwaverider_processor.upload_all()
            if not aiwaverider_result:
                logger.log_error("AIWaverider upload failed")
                return False
            
            # Update database and sheets after AIWaverider uploads
            logger.log_step("Updating database and sheets after AIWaverider uploads...")
            await self._update_database_and_sheets_after_step("aiwaverider_upload")
            
            # Step 4: Sheets Update
            logger.log_step("Step 4: Google Sheets update")
            sheets_result = await self.sheets_processor.update_master_sheet()
            if not sheets_result:
                logger.log_error("Sheets update failed")
                return False
            
            # Step 5: Excel Generation and Upload
            logger.log_step("Step 5: Video transcripts sheet update")
            transcripts_result = await self.transcripts_sheets_processor.update_transcripts_sheet()
            if not transcripts_result:
                logger.log_error("Transcripts sheet update failed")
                return False
            
            logger.log_step("Pipeline processing completed successfully")
            return True
            
        except Exception as e:
            logger.log_error(f"Error in pipeline processing: {str(e)}")
            return False
    
    async def _update_database_and_sheets_after_step(self, step_name: str):
        """Update database and sheets after each processing step"""
        try:
            logger.log_step(f"Updating database and sheets after {step_name}")
            
            # Update master sheet
            sheets_result = await self.sheets_processor.update_master_sheet()
            if sheets_result:
                logger.log_step(f"✅ Master sheet updated after {step_name}")
            else:
                logger.log_error(f"❌ Master sheet update failed after {step_name}")
            
            # Update transcripts sheet
            transcripts_result = await self.transcripts_sheets_processor.update_transcripts_sheet()
            if transcripts_result:
                logger.log_step(f"✅ Transcripts sheet updated after {step_name}")
            else:
                logger.log_error(f"❌ Transcripts sheet update failed after {step_name}")
                
        except Exception as e:
            logger.log_error(f"Error updating database and sheets after {step_name}: {str(e)}")
    
    async def cleanup(self):
        """Cleanup all resources"""
        try:
            logger.log_step("Starting cleanup process")
            
            # Stop queue processor
            await queue_processor.stop()
            logger.log_step("Queue processor stopped")
            
            # Cleanup all processors
            for processor in self.processing_pipeline:
                await processor.cleanup()
                logger.log_step(f"Cleaned up {processor.__class__.__name__}")
            
            # Close database
            await db_manager.close()
            logger.log_step("Database connections closed")
            
            # Finish metrics
            metrics_collector.finish_processing_metrics()
            logger.log_step("Metrics collection finished")
            
            logger.log_step("Cleanup completed successfully")
            
        except Exception as e:
            logger.log_error(f"Error during cleanup: {str(e)}")
    
    async def process_existing_videos(self) -> bool:
        """Process existing videos without downloading (transcription + upload only)"""
        try:
            logger.log_step("Starting processing of existing videos (skipping download)")
            
            # Ensure database is initialized
            if not db_manager._initialized:
                await db_manager.initialize()
            
            # Step 1: Process existing videos for transcription
            logger.log_step("Step 1: Processing existing videos for transcription")
            video_results = await self.video_processor.process_existing_videos()
            if not video_results:
                logger.log_step("Video processing had issues, but continuing with uploads for completed videos")
            else:
                logger.log_step("Video processing completed successfully")
            
            # Update database and sheets after video processing
            logger.log_step("Updating database and sheets after video processing...")
            await self._update_database_and_sheets_after_step("video_processing")
            
            # Always continue with uploads regardless of video processing results
            logger.log_step("Continuing with upload processing for any successfully processed videos")
            
            # Step 2: Google Drive Upload Processing (parallel with thumbnails)
            logger.log_step("Step 2: Google Drive upload processing")
            upload_tasks = [
                self.upload_processor.process_videos(),
                self.upload_processor.process_thumbnails()
            ]
            
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Check for upload errors
            for i, result in enumerate(upload_results):
                if isinstance(result, Exception):
                    logger.log_error(f"Google Drive upload task {i} failed: {str(result)}")
                elif not result:
                    logger.log_error(f"Google Drive upload task {i} returned False")
            
            # Update database and sheets after Google Drive uploads
            logger.log_step("Updating database and sheets after Google Drive uploads...")
            await self._update_database_and_sheets_after_step("google_drive_upload")
            
            # Step 3: AIWaverider Upload (videos and thumbnails)
            logger.log_step("Step 3: AIWaverider Drive upload (videos and thumbnails)")
            aiwaverider_result = await self.aiwaverider_processor.upload_all()
            if not aiwaverider_result:
                logger.log_error("AIWaverider upload failed")
                return False
            
            # Update database and sheets after AIWaverider uploads
            logger.log_step("Updating database and sheets after AIWaverider uploads...")
            await self._update_database_and_sheets_after_step("aiwaverider_upload")
            
            # Step 4: Sheets Update
            logger.log_step("Step 4: Google Sheets update")
            sheets_result = await self.sheets_processor.update_master_sheet()
            if not sheets_result:
                logger.log_error("Sheets update failed")
                return False
            
            # Update transcripts sheet
            transcripts_result = await self.transcripts_sheets_processor.update_transcripts_sheet()
            if not transcripts_result:
                logger.log_error("Transcripts sheet update failed")
                return False
            
            logger.log_step("Existing videos processing completed successfully")
            return True
            
        except Exception as e:
            logger.log_error(f"Error processing existing videos: {str(e)}")
            return False
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            health_status = await metrics_collector.get_health_status()
            queue_status = await queue_processor.get_queue_status()
            
            return {
                'health': health_status,
                'queue': queue_status,
                'processors': {
                    processor.__class__.__name__: await processor.get_status()
                    for processor in self.processing_pipeline
                }
            }
        except Exception as e:
            logger.log_error(f"Error getting system status: {str(e)}")
            return {'error': str(e)}


async def main():
    """Main entry point"""
    orchestrator = SocialMediaOrchestrator()
    
    try:
        # Initialize
        if not await orchestrator.initialize():
            logger.log_error("Failed to initialize orchestrator")
            return
        
        # Load URLs
        urls_file = 'data/urls.txt'
        if not os.path.exists(urls_file):
            logger.log_error(f"URLs file not found: {urls_file}")
            return
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not urls:
            logger.log_error("No URLs found to process")
            return
        
        # Process URLs
        success = await orchestrator.process_urls(urls)
        
        if success:
            logger.log_step("Processing completed successfully")
        else:
            logger.log_error("Processing failed")
        
        # Get final status
        status = await orchestrator.get_system_status()
        logger.log_step(f"System health: {status['health']['overall_status']}")
        logger.log_step(f"Queue status: {status['queue']['pending_tasks']} pending tasks")
        
    except Exception as e:
        logger.log_error(f"Fatal error in main: {str(e)}")
    finally:
        # Always cleanup
        await orchestrator.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
