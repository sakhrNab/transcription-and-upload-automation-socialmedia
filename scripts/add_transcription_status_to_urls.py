#!/usr/bin/env python3
"""
Migration script to add transcription_status column to urls table
"""

import sqlite3
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def migrate_urls_table():
    """Add transcription_status column to urls table if it doesn't exist"""
    # Try to find the database file
    db_paths = [
        project_root / "db" / "social_media.db",
        project_root / "social_media.db",
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print(f"ERROR: Database file not found. Tried: {[str(p) for p in db_paths]}")
        return False
    
    print(f"Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if urls table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
        if not cursor.fetchone():
            print("ERROR: urls table does not exist!")
            conn.close()
            return False
        
        # Check if transcription_status column exists
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'transcription_status' in columns:
            print("[OK] transcription_status column already exists in urls table")
            conn.close()
            return True
        
        # Add the column
        print("Adding transcription_status column to urls table...")
        cursor.execute("ALTER TABLE urls ADD COLUMN transcription_status TEXT DEFAULT 'PENDING'")
        conn.commit()
        
        # Verify it was added
        cursor.execute("PRAGMA table_info(urls)")
        columns_after = [col[1] for col in cursor.fetchall()]
        
        if 'transcription_status' in columns_after:
            print("[OK] Successfully added transcription_status column to urls table")
            
            # Now sync existing transcription_status from video_transcripts table
            print("\nSyncing transcription_status from video_transcripts table...")
            cursor.execute("""
                UPDATE urls 
                SET transcription_status = (
                    SELECT transcription_status 
                    FROM video_transcripts 
                    WHERE video_transcripts.video_id = urls.video_id
                    LIMIT 1
                )
                WHERE video_id IS NOT NULL 
                AND EXISTS (
                    SELECT 1 FROM video_transcripts 
                    WHERE video_transcripts.video_id = urls.video_id
                )
            """)
            updated_count = cursor.rowcount
            conn.commit()
            print(f"[OK] Synced transcription_status for {updated_count} URL(s)")
            
            conn.close()
            return True
        else:
            print("ERROR: Failed to add transcription_status column")
            conn.close()
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        if conn:
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add transcription_status to urls table")
    print("=" * 60)
    success = migrate_urls_table()
    if success:
        print("\n[SUCCESS] Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n[FAILED] Migration failed!")
        sys.exit(1)

