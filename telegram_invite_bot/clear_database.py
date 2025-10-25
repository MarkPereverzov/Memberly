"""
Script to clear all data from the database
"""
import sqlite3
import os

def clear_database():
    """Clear all data from database tables"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'data', 'bot_database.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        print(f"📊 Found {len(tables)} tables in database")
        
        # Clear each table
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DELETE FROM {table_name}")
            deleted = cursor.rowcount
            print(f"✅ Cleared table '{table_name}': {deleted} rows deleted")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Database cleared successfully!")
        print("📋 All user data, accounts, groups, whitelist, and blacklist have been removed.")
        
    except sqlite3.Error as e:
        print(f"❌ Error clearing database: {e}")

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL data from the database!")
    print("This includes:")
    print("  - All user accounts")
    print("  - All groups")
    print("  - Whitelist entries")
    print("  - Blacklist entries")
    print("  - User information")
    print("  - All statistics\n")
    
    confirmation = input("Are you sure you want to continue? (yes/no): ")
    
    if confirmation.lower() == 'yes':
        clear_database()
    else:
        print("❌ Operation cancelled.")
