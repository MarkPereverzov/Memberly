#!/usr/bin/env python3
"""
Database structure migration script
Migrates from separate group_statistics table to member_count column in groups table
"""

import sqlite3
import logging
import os
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_database_structure(db_path: str = None) -> bool:
    """
    Migrate database structure:
    1. Add member_count and last_updated columns to groups table
    2. Copy data from group_statistics to groups table
    3. Drop group_statistics table
    """
    if db_path is None:
        # Use project root data directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data')
        db_path = os.path.join(data_dir, "bot_database.db")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Create backup
        backup_path = f"{db_path}.backup_{int(time.time())}"
        logger.info(f"📦 Creating backup: {backup_path}")
        
        with open(db_path, 'rb') as original:
            with open(backup_path, 'wb') as backup:
                backup.write(original.read())
        
        logger.info("✅ Backup created successfully")
        
        # Perform migration
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            logger.info("🔄 Starting database structure migration...")
            
            # Check if group_statistics table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='group_statistics'
            """)
            
            stats_table_exists = cursor.fetchone() is not None
            
            if stats_table_exists:
                logger.info("📊 Found group_statistics table, migrating data...")
                
                # Add new columns to groups table if they don't exist
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN member_count INTEGER DEFAULT 0')
                    logger.info("✅ Added member_count column to groups table")
                except sqlite3.OperationalError:
                    logger.info("ℹ️ member_count column already exists")
                
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN last_updated REAL DEFAULT 0')
                    logger.info("✅ Added last_updated column to groups table")
                except sqlite3.OperationalError:
                    logger.info("ℹ️ last_updated column already exists")
                
                # Copy data from group_statistics to groups
                cursor.execute("""
                    UPDATE groups 
                    SET member_count = (
                        SELECT member_count 
                        FROM group_statistics 
                        WHERE group_statistics.group_id = groups.group_id
                    ),
                    last_updated = (
                        SELECT last_updated 
                        FROM group_statistics 
                        WHERE group_statistics.group_id = groups.group_id
                    )
                    WHERE group_id IN (
                        SELECT group_id FROM group_statistics
                    )
                """)
                
                migrated_count = cursor.rowcount
                logger.info(f"✅ Migrated statistics for {migrated_count} groups")
                
                # Drop the old table
                cursor.execute('DROP TABLE group_statistics')
                logger.info("🗑️ Dropped old group_statistics table")
                
            else:
                logger.info("ℹ️ No group_statistics table found, adding columns to groups table...")
                
                # Just add the columns if the table doesn't exist
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN member_count INTEGER DEFAULT 0')
                    logger.info("✅ Added member_count column to groups table")
                except sqlite3.OperationalError:
                    logger.info("ℹ️ member_count column already exists")
                
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN last_updated REAL DEFAULT 0')
                    logger.info("✅ Added last_updated column to groups table")
                except sqlite3.OperationalError:
                    logger.info("ℹ️ last_updated column already exists")
            
            # Verify migration
            cursor.execute("PRAGMA table_info(groups)")
            columns = [column[1] for column in cursor.fetchall()]
            
            required_columns = ['group_id', 'group_name', 'invite_link', 'is_active', 'assigned_accounts', 'member_count', 'last_updated']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                logger.error(f"❌ Migration incomplete. Missing columns: {missing_columns}")
                return False
            
            # Check that group_statistics table is gone
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='group_statistics'
            """)
            
            if cursor.fetchone() is not None:
                logger.error("❌ group_statistics table still exists after migration")
                return False
            
            conn.commit()
            logger.info("✅ Database structure migration completed successfully!")
            
            # Show final structure
            cursor.execute("SELECT COUNT(*) FROM groups")
            group_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM groups WHERE member_count > 0")
            groups_with_stats = cursor.fetchone()[0]
            
            logger.info(f"📊 Final status:")
            logger.info(f"   • Total groups: {group_count}")
            logger.info(f"   • Groups with member count: {groups_with_stats}")
            
            return True
            
    except sqlite3.Error as e:
        logger.error(f"❌ Database error during migration: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during migration: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 Database Structure Migration")
    print("=" * 50)
    print("This script will migrate your database structure:")
    print("• Add member_count and last_updated columns to groups table")
    print("• Migrate data from group_statistics table (if exists)")
    print("• Remove the old group_statistics table")
    print("• Create a backup before making changes")
    print()
    
    # Confirm migration
    response = input("Do you want to proceed with the migration? (y/n): ").lower().strip()
    if response != 'y':
        print("Migration cancelled.")
        return
    
    # Perform migration
    success = migrate_database_structure()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("Your database has been updated to use the new structure.")
    else:
        print("\n❌ Migration failed!")
        print("Check the logs above for details.")
        print("Your original database is backed up.")

if __name__ == "__main__":
    main()