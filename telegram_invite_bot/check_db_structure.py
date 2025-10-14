#!/usr/bin/env python3
"""Check database structure"""

import sqlite3

def check_db_structure():
    db_path = 'data/bot_database.db'
    
    print("="*60)
    print("DATABASE STRUCTURE CHECK")
    print("="*60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\nTables in database:")
        for table in tables:
            print(f"   {table[0]}")
        
        # Check each table structure
        for table in tables:
            table_name = table[0]
            print(f"\n{table_name} table structure:")
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   {col[1]} ({col[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    check_db_structure()