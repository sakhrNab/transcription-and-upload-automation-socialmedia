#!/usr/bin/env python3
"""
Script to sync transcription_status from video_transcripts to urls table
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def sync_transcription_status():
    """Sync transcription_status from video_transcripts to urls table"""
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
        
        # Check if transcription_status column exists in urls table
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'transcription_status' not in columns:
            print("ERROR: transcription_status column does not exist in urls table!")
            print("Please run add_transcription_status_to_urls.py first")
            conn.close()
            return False
        
        # Sync transcription_status from video_transcripts to urls
        print("\nSyncing transcription_status from video_transcripts to urls table...")
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
        
        # Show sync results
        print("\nVerifying sync...")
        cursor.execute("""
            SELECT 
                u.url, 
                u.video_id, 
                u.transcription_status as url_status, 
                v.transcription_status as video_status
            FROM urls u 
            LEFT JOIN video_transcripts v ON u.video_id = v.video_id 
            WHERE u.video_id IS NOT NULL
            ORDER BY u.created_at DESC
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        print("\nSync Results (first 10):")
        print("-" * 80)
        mismatched = 0
        for row in results:
            url, video_id, url_status, video_status = row
            status_match = "OK" if url_status == video_status else "MISMATCH"
            if url_status != video_status:
                mismatched += 1
            print(f"  video_id: {video_id}")
            print(f"    URL status: {url_status} | Video status: {video_status} [{status_match}]")
            print()
        
        if mismatched > 0:
            print(f"WARNING: {mismatched} URL(s) still have mismatched status")
        else:
            print("[OK] All URLs are in sync!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Sync: transcription_status from video_transcripts to urls")
    print("=" * 60)
    success = sync_transcription_status()
    if success:
        print("\n[SUCCESS] Sync completed!")
        sys.exit(0)
    else:
        print("\n[FAILED] Sync failed!")
        sys.exit(1)

