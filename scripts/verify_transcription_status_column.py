#!/usr/bin/env python3
"""
Script to verify transcription_status column exists in urls table
"""

import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent

def check_database(db_path, db_name):
    """Check if transcription_status column exists"""
    if not db_path.exists():
        print(f"\n{db_name}: File not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if urls table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
        if not cursor.fetchone():
            print(f"\n{db_name}: urls table does not exist")
            conn.close()
            return False
        
        # Get all columns
        cursor.execute("PRAGMA table_info(urls)")
        columns = cursor.fetchall()
        
        print(f"\n{'='*70}")
        print(f"{db_name}: {db_path}")
        print(f"{'='*70}")
        print(f"\nColumns in urls table ({len(columns)} total):")
        print("-" * 70)
        
        has_transcription_status = False
        for i, col in enumerate(columns, 1):
            col_name = col[1]
            col_type = col[2]
            is_transcription_status = col_name == 'transcription_status'
            if is_transcription_status:
                has_transcription_status = True
                print(f"  {i:2d}. {col_name:25s} ({col_type:15s}) <-- FOUND!")
            else:
                print(f"  {i:2d}. {col_name:25s} ({col_type:15s})")
        
        if has_transcription_status:
            print("\n[OK] transcription_status column EXISTS!")
            
            # Show sample data
            cursor.execute("SELECT url, video_id, transcription_status FROM urls LIMIT 5")
            rows = cursor.fetchall()
            if rows:
                print("\nSample data:")
                print("-" * 70)
                for row in rows:
                    url, video_id, status = row
                    url_short = url[:50] + "..." if len(url) > 50 else url
                    print(f"  URL: {url_short}")
                    print(f"    video_id: {video_id or 'NULL'}")
                    print(f"    transcription_status: {status}")
                    print()
        else:
            print("\n[ERROR] transcription_status column NOT FOUND!")
            print("\nYou need to run: python scripts/add_transcription_status_to_urls.py")
        
        conn.close()
        return has_transcription_status
        
    except Exception as e:
        print(f"\n{db_name}: ERROR - {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Verifying transcription_status column in urls table")
    print("=" * 70)
    
    # Check main database
    main_db = project_root / "db" / "social_media.db"
    check_database(main_db, "Main Database")
    
    print("\n" + "=" * 70)
    print("Verification Complete")
    print("=" * 70)

