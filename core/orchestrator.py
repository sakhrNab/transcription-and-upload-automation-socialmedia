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
from system.database import db_manager
from system.queue_processor import queue_processor
from system.health_metrics import metrics_collector

# Import processors
from core.processors.video_processor import VideoProcessor
from core.processors.upload_processor import UploadProcessor
from core.processors.thumbnail_processor import ThumbnailProcessor
from core.processors.aiwaverider_processor import AIWaveriderProcessor
from core.processors.sheets_processor import SheetsProcessor
from core.processors.excel_processor import ExcelProcessor


class SocialMediaOrchestrator:
    """Main orchestrator that coordinates all processing components"""
    
    def __init__(self):
        """Initialize the orchestrator with all processors"""
        self.video_processor = VideoProcessor()
        self.upload_processor = UploadProcessor()
        self.thumbnail_processor = ThumbnailProcessor()
        self.aiwaverider_processor = AIWaveriderProcessor()
        self.sheets_processor = SheetsProcessor()
        self.excel_processor = ExcelProcessor()
        
        self.processing_pipeline = [
            self.video_processor,
            self.upload_processor,
            self.thumbnail_processor,
            self.aiwaverider_processor,
            self.sheets_processor,
            self.excel_processor
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
                logger.log_error("Video processing failed")
                return False
            
            # Step 2: Upload Processing (parallel with thumbnails)
            logger.log_step("Step 2: Upload processing")
            upload_tasks = [
                self.upload_processor.process_videos(),
                self.thumbnail_processor.process_thumbnails()
            ]
            
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Check for upload errors
            for i, result in enumerate(upload_results):
                if isinstance(result, Exception):
                    logger.log_error(f"Upload task {i} failed: {str(result)}")
                elif not result:
                    logger.log_error(f"Upload task {i} returned False")
            
            # Step 3: AIWaverider Upload
            logger.log_step("Step 3: AIWaverider Drive upload")
            aiwaverider_result = await self.aiwaverider_processor.upload_all()
            if not aiwaverider_result:
                logger.log_error("AIWaverider upload failed")
                return False
            
            # Step 4: Sheets Update
            logger.log_step("Step 4: Google Sheets update")
            sheets_result = await self.sheets_processor.update_master_sheet()
            if not sheets_result:
                logger.log_error("Sheets update failed")
                return False
            
            # Step 5: Excel Generation and Upload
            logger.log_step("Step 5: Excel file generation and upload")
            excel_result = await self.excel_processor.generate_and_upload_excel()
            if not excel_result:
                logger.log_error("Excel generation and upload failed")
                return False
            
            logger.log_step("Pipeline processing completed successfully")
            return True
            
        except Exception as e:
            logger.log_error(f"Error in pipeline processing: {str(e)}")
            return False
    
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
