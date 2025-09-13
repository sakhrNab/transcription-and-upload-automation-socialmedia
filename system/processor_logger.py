"""
Logging system for social media processor
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path

class ProcessorLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this session
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Set up file handlers
        self.setup_logging()
        
        # Store session data
        self.session_data = {
            'start_time': datetime.now().isoformat(),
            'session_id': self.session_id,
            'steps': [],
            'errors': [],
            'uploads': []
        }
    
    def setup_logging(self):
        # Main logger
        self.logger = logging.getLogger('processor')
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler with color formatting
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console.setFormatter(console_format)
        
        # File handler
        log_file = self.log_dir / f'processor_{self.session_id}.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Add handlers
        self.logger.addHandler(console)
        self.logger.addHandler(file_handler)
    
    def log_step(self, step_name, details=None):
        """Log a processing step"""
        msg = f"STEP: {step_name}"
        if details:
            msg += f" - {json.dumps(details)}"
        self.logger.info(msg)
        
        self.session_data['steps'].append({
            'timestamp': datetime.now().isoformat(),
            'step': step_name,
            'details': details or {}
        })
        self._save_session()
    
    def log_error(self, error_msg, error_type=None, details=None):
        """Log an error with context"""
        msg = f"ERROR: {error_msg}"
        if error_type:
            msg = f"{error_type}: {msg}"
        self.logger.error(msg)
        
        self.session_data['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'error': error_msg,
            'type': error_type,
            'details': details or {}
        })
        self._save_session()
    
    def log_upload(self, file_type, file_name, drive_id=None, status=None):
        """Log a file upload"""
        msg = f"UPLOAD: {file_type} - {file_name}"
        if drive_id:
            msg += f" (Drive ID: {drive_id})"
        if status:
            msg += f" - {status}"
        self.logger.info(msg)
        
        self.session_data['uploads'].append({
            'timestamp': datetime.now().isoformat(),
            'file_type': file_type,
            'file_name': file_name,
            'drive_id': drive_id,
            'status': status
        })
        self._save_session()
    
    def _save_session(self):
        """Save session data to JSON file"""
        session_file = self.log_dir / f'session_{self.session_id}.json'
        with open(session_file, 'w') as f:
            json.dump(self.session_data, f, indent=2)

# Global logger instance
processor_logger = ProcessorLogger()