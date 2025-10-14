#!/usr/bin/env python3
"""Initialize database manually"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager import DatabaseManager

def init_database():
    print("="*60)
    print("INITIALIZING DATABASE")
    print("="*60)
    
    try:
        # Initialize database manager (this should create tables)
        db_manager = DatabaseManager('data/bot_database.db')
        print("✅ Database initialized successfully")
        
        # Check what tables were created
        import sqlite3
        with sqlite3.connect('data/bot_database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print(f"\nTables created: {len(tables)}")
            for table in tables:
                print(f"   ✅ {table[0]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)

if __name__ == "__main__":
    init_database()