#!/usr/bin/env python3
"""
Check database tables and their content
"""

import sqlite3

def check_database():
    """Check all tables in the database"""
    try:
        conn = sqlite3.connect('social_media.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("🗄️  DATABASE TABLES:")
        print("=" * 50)
        
        for table in tables:
            table_name = table[0]
            print(f"\n📋 Table: {table_name}")
            print("-" * 30)
            
            # Count rows
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Rows: {count}")
            
            if count > 0:
                # Get column names
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"   Columns: {[col[1] for col in columns]}")
                
                # Show sample data
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                sample_data = cursor.fetchall()
                print(f"   Sample data:")
                for i, row in enumerate(sample_data):
                    print(f"     {i+1}. {row}")
            else:
                print("   ⚠️  Table is empty")
        
        conn.close()
        print("\n✅ Database check complete!")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_database()

