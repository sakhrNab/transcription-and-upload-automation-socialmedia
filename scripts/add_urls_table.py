#!/usr/bin/env python3
"""
Add URLs table to existing database
"""

import sqlite3
import sys
from pathlib import Path

def add_urls_table(db_path):
    """Add URLs table to existing database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create URLs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'PENDING',
                download_status TEXT DEFAULT 'PENDING',
                video_id TEXT,
                downloaded_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES video_transcripts(video_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_url ON urls(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status)")
        
        conn.commit()
        
        # Verify table was created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
        exists = cursor.fetchone()
        
        if exists:
            print(f"✅ URLs table created successfully in {db_path}")
        else:
            print(f"❌ Failed to create URLs table in {db_path}")
        
        conn.close()
        return exists is not None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Try to find the database
    db_paths = [
        "db/social_media.db",
        Path(__file__).parent.parent / "db" / "social_media.db",
        "social_media.db"
    ]
    
    db_path = None
    for path in db_paths:
        if isinstance(path, Path):
            if path.exists():
                db_path = str(path)
                break
        elif Path(path).exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ Database not found. Please ensure db/social_media.db exists.")
        sys.exit(1)
    
    print(f"📁 Using database: {db_path}")
    success = add_urls_table(db_path)
    sys.exit(0 if success else 1)

