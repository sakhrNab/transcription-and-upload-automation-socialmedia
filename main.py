#!/usr/bin/env python3
"""
Main Entry Point for Social Media Processor
Simple launcher for the refactored system
"""

import sys
import os
import asyncio

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import and run the main processor
from core.social_media_processor import main

if __name__ == "__main__":
    print("🚀 Starting Social Media Processor...")
    print("📁 Refactored codebase structure:")
    print("   • core/ - Main application files")
    print("   • system/ - Infrastructure and utilities")
    print("   • scripts/ - Upload and utility scripts")
    print("   • data/ - Database schema and data files")
    print("   • docs/ - Documentation")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
