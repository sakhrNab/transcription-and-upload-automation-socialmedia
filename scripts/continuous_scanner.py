#!/usr/bin/env python3
"""
Continuous Scanner Service
Monitors assets/finished_videos/ for new videos and automatically uploads them
"""

import asyncio
import os
import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Set, Dict, Any
import json
from datetime import datetime

# Fix Unicode display on Windows
if sys.platform == "win32":
    import codecs
    if hasattr(sys.stdout, 'detach'):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import SocialMediaOrchestrator
from system.new_database import new_db_manager
from system.config import settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('continuous_scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VideoUploadHandler(FileSystemEventHandler):
    """Handles file system events for video uploads"""
    
    def __init__(self, scanner_service):
        self.scanner_service = scanner_service
        self.processed_files: Set[str] = set()
        self.pending_files: Dict[str, float] = {}  # file_path -> timestamp
        self.debounce_delay = 2.0  # Wait 2 seconds before processing
        
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        if file_path.endswith('.mp4'):
            logger.info(f"New video detected: {file_path}")
            self.pending_files[file_path] = time.time()
            # Schedule processing after debounce delay
            asyncio.create_task(self._process_after_delay(file_path))
    
    def on_moved(self, event):
        """Handle file move events"""
        if event.is_directory:
            return
            
        file_path = event.dest_path
        if file_path.endswith('.mp4'):
            logger.info(f"Video moved to finished_videos: {file_path}")
            self.pending_files[file_path] = time.time()
            # Schedule processing after debounce delay
            asyncio.create_task(self._process_after_delay(file_path))
    
    async def _process_after_delay(self, file_path: str):
        """Process file after debounce delay"""
        await asyncio.sleep(self.debounce_delay)
        
        # Check if file still exists and hasn't been processed
        if (os.path.exists(file_path) and 
            file_path not in self.processed_files and
            file_path in self.pending_files):
            
            # Remove from pending
            del self.pending_files[file_path]
            
            # Process the file
            await self.scanner_service.process_video(file_path)
            self.processed_files.add(file_path)

class ContinuousScannerService:
    """Continuous scanner service for automatic video uploads"""
    
    def __init__(self):
        self.orchestrator = None
        self.observer = None
        self.running = False
        self.watch_directory = Path("assets/finished_videos")
        self.state_file = "scanner_state.json"
        self.processed_files = set()
        
    async def initialize(self):
        """Initialize the scanner service"""
        try:
            logger.info("Initializing Continuous Scanner Service")
            
            # Create watch directory if it doesn't exist
            self.watch_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Watching directory: {self.watch_directory}")
            
            # Initialize orchestrator
            # Initialize new database
            logger.info("Initializing new database...")
            await new_db_manager.initialize()
            logger.info("New database initialized")
            
            # Initialize orchestrator
            logger.info("Initializing orchestrator...")
            self.orchestrator = SocialMediaOrchestrator()
            await self.orchestrator.initialize()
            logger.info("Orchestrator initialized")
            
            # Load previous state
            await self._load_state()
            
            # Set up file system watcher
            self.event_handler = VideoUploadHandler(self)
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler, 
                str(self.watch_directory), 
                recursive=True
            )
            
            logger.info("Continuous Scanner Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize scanner service: {str(e)}")
            return False
    
    async def start(self):
        """Start the continuous scanner"""
        try:
            if not self.orchestrator:
                logger.error("Scanner not initialized. Call initialize() first.")
                return False
            
            logger.info("Starting continuous scanner...")
            self.running = True
            
            # Start file system observer
            self.observer.start()
            logger.info(f"Watching for new videos in {self.watch_directory}")
            
            # Process any existing videos that haven't been uploaded
            await self._process_existing_videos()
            
            # Main monitoring loop
            while self.running:
                try:
                    await asyncio.sleep(1)  # Check every second
                    
                    # Save state periodically
                    if int(time.time()) % 60 == 0:  # Every minute
                        await self._save_state()
                        
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {str(e)}")
                    await asyncio.sleep(5)  # Wait before retrying
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting scanner: {str(e)}")
            return False
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the continuous scanner"""
        try:
            logger.info("Stopping continuous scanner...")
            self.running = False
            
            if self.observer:
                self.observer.stop()
                self.observer.join()
                logger.info("File system observer stopped")
            
            # Save final state
            await self._save_state()
            
            # Cleanup orchestrator
            if self.orchestrator:
                await self.orchestrator.cleanup()
                logger.info("Orchestrator cleaned up")
            
            logger.info("Continuous scanner stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scanner: {str(e)}")
    
    async def process_video(self, file_path: str):
        """Process a single video for upload"""
        try:
            logger.info(f"Processing video: {file_path}")
            
            # Check if already processed
            if file_path in self.processed_files:
                logger.info(f"Video already processed: {file_path}")
                return True
            
            # Check if file exists and is valid
            if not os.path.exists(file_path) or not file_path.endswith('.mp4'):
                logger.warning(f"Invalid file or not found: {file_path}")
                return False
            
            # Get file info
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            
            if file_size == 0:
                logger.warning(f"Empty file, skipping: {file_path}")
                return False
            
            logger.info(f"File size: {file_size / (1024*1024):.2f} MB")
            
            # Extract video_id from filename (assuming format like "01_username_videoID.mp4")
            filename = os.path.basename(file_path)
            video_id = filename.split('_')[-1].replace('.mp4', '') if '_' in filename else filename.replace('.mp4', '')
            
            # Check if video has already been uploaded to both platforms
            logger.info(f"Checking upload status for video_id: {video_id}")
            
            is_uploaded = await new_db_manager.is_file_uploaded(video_id, 'video', 'both')
            if is_uploaded:
                logger.info(f"Video {video_id} already uploaded to both Google Drive and AIWaverider. Skipping.")
                self.processed_files.add(file_path)
                await self._save_state()
                return True
            
            # Check individual platform status
            gdrive_uploaded = await new_db_manager.is_file_uploaded(video_id, 'video', 'gdrive')
            aiwaverider_uploaded = await new_db_manager.is_file_uploaded(video_id, 'video', 'aiwaverider')
            
            logger.info(f"Upload status - Google Drive: {'YES' if gdrive_uploaded else 'NO'}, AIWaverider: {'YES' if aiwaverider_uploaded else 'NO'}")
            
            # Process uploads using orchestrator
            logger.info("Starting upload process...")
            
            # Run upload processors
            upload_success = await self.orchestrator.upload_processor.process_videos()
            thumbnail_success = await self.orchestrator.thumbnail_processor.process_thumbnails()
            aiwaverider_success = await self.orchestrator.aiwaverider_processor.upload_all()
            
            # Update sheets
            sheets_success = await self.orchestrator.sheets_processor.update_master_sheet()
            transcripts_success = await self.orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
            
            # Check results
            if upload_success and thumbnail_success and aiwaverider_success and sheets_success and transcripts_success:
                logger.info(f"Successfully processed video: {file_path}")
                self.processed_files.add(file_path)
                await self._save_state()
                return True
            else:
                logger.error(f"Failed to process video: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing video {file_path}: {str(e)}")
            return False
    
    async def _process_existing_videos(self):
        """Process any existing videos in the finished_videos directory"""
        try:
            logger.info("Checking for existing videos to process...")
            
            existing_videos = []
            for mp4_file in self.watch_directory.rglob("*.mp4"):
                file_path = str(mp4_file)
                if file_path not in self.processed_files:
                    existing_videos.append(file_path)
            
            if existing_videos:
                logger.info(f"Found {len(existing_videos)} existing videos to process")
                for video_path in existing_videos:
                    await self.process_video(video_path)
            else:
                logger.info("📭 No existing videos to process")
                
        except Exception as e:
            logger.error(f"Error processing existing videos: {str(e)}")
    
    async def _load_state(self):
        """Load scanner state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.processed_files = set(state.get('processed_files', []))
                    logger.info(f"Loaded state: {len(self.processed_files)} processed files")
            else:
                logger.info("No previous state found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading state: {str(e)}")
            self.processed_files = set()
    
    async def _save_state(self):
        """Save scanner state to file"""
        try:
            state = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {str(e)}")

async def main():
    """Main function for continuous scanner"""
    scanner = ContinuousScannerService()
    
    try:
        # Initialize scanner
        if not await scanner.initialize():
            logger.error("Failed to initialize scanner service")
            return False
        
        # Start continuous monitoring
        logger.info("Starting continuous video upload scanner...")
        logger.info("Place videos in assets/finished_videos/ to trigger automatic uploads")
        logger.info("Press Ctrl+C to stop")
        
        await scanner.start()
        
    except KeyboardInterrupt:
        logger.info("Scanner interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        await scanner.stop()

if __name__ == "__main__":
    asyncio.run(main())
