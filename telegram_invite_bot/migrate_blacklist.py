#!/usr/bin/env python3
"""
Database migration script to add blacklist table
"""
import os
import sys
import sqlite3
import logging
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_backup(db_path: str) -> str:
    """Create backup of the database"""
    timestamp = int(time.time())
    backup_path = f"{db_path}.backup_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise

def add_blacklist_table(db_path: str) -> bool:
    """Add blacklist table to existing database"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if blacklist table already exists
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='blacklist'
            ''')
            
            if cursor.fetchone():
                logger.info("Blacklist table already exists, skipping creation")
                return True
            
            # Create blacklist table
            cursor.execute('''
                CREATE TABLE blacklist (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    reason TEXT NOT NULL,
                    added_by INTEGER NOT NULL,
                    added_date REAL NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Create index for better performance
            cursor.execute('''
                CREATE INDEX idx_blacklist_user 
                ON blacklist(user_id)
            ''')
            
            conn.commit()
            logger.info("Blacklist table created successfully")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def verify_migration(db_path: str) -> bool:
    """Verify that migration was successful"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if blacklist table exists
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='blacklist'
            ''')
            
            if not cursor.fetchone():
                logger.error("Blacklist table not found after migration")
                return False
            
            # Check table structure
            cursor.execute('PRAGMA table_info(blacklist)')
            columns = cursor.fetchall()
            
            expected_columns = ['user_id', 'username', 'reason', 'added_by', 'added_date', 'is_active']
            actual_columns = [col[1] for col in columns]
            
            for expected_col in expected_columns:
                if expected_col not in actual_columns:
                    logger.error(f"Missing column: {expected_col}")
                    return False
            
            # Check index exists
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_blacklist_user'
            ''')
            
            if not cursor.fetchone():
                logger.warning("Blacklist index not found, but table is functional")
            
            logger.info("Migration verification completed successfully")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Verification failed: {e}")
        return False

def main():
    """Main migration function"""
    # Database path - use project root data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data')
    db_path = os.path.join(data_dir, "bot_database.db")
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return 1
    
    logger.info("Starting blacklist table migration...")
    
    try:
        # Create backup
        backup_path = create_backup(db_path)
        
        # Add blacklist table
        if not add_blacklist_table(db_path):
            logger.error("Failed to add blacklist table")
            return 1
        
        # Verify migration
        if not verify_migration(db_path):
            logger.error("Migration verification failed")
            return 1
        
        logger.info("✅ Blacklist table migration completed successfully!")
        logger.info(f"📁 Backup created at: {backup_path}")
        
        # Show current database structure
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"📊 Current tables: {', '.join(tables)}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())