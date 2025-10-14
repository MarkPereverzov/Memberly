#!/usr/bin/env python3
"""
Migration script to move data from JSON files to database
"""
import os
import sys
import json
import shutil
from pathlib import Path

# Add path to project
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database_manager import DatabaseManager

def backup_json_files():
    """Create backup of JSON files"""
    print("📦 Creating backup of JSON files...")
    
    config_dir = "config"
    backup_dir = "config/backup"
    
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = ["accounts.json", "groups.json"]
    
    for filename in files_to_backup:
        src_path = os.path.join(config_dir, filename)
        backup_path = os.path.join(backup_dir, f"{filename}.backup")
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, backup_path)
            print(f"✅ Backed up {filename}")
        else:
            print(f"⚠️  File {filename} not found")

def load_json_data():
    """Load data from JSON files"""
    print("📖 Loading data from JSON files...")
    
    accounts_data = []
    groups_data = []
    
    # Load accounts
    accounts_file = "config/accounts.json"
    if os.path.exists(accounts_file):
        with open(accounts_file, 'r', encoding='utf-8') as f:
            accounts_data = json.load(f)
        print(f"✅ Loaded {len(accounts_data)} accounts")
    else:
        print("⚠️  accounts.json not found")
    
    # Load groups
    groups_file = "config/groups.json"
    if os.path.exists(groups_file):
        with open(groups_file, 'r', encoding='utf-8') as f:
            groups_data = json.load(f)
        print(f"✅ Loaded {len(groups_data)} groups")
    else:
        print("⚠️  groups.json not found")
    
    return accounts_data, groups_data

def migrate_to_database(accounts_data, groups_data):
    """Migrate data to database"""
    print("🔄 Migrating data to database...")
    
    try:
        # Initialize database manager - use project root data directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data')
        db_path = os.path.join(data_dir, "bot_database.db")
        db_manager = DatabaseManager(db_path)
        
        # Migrate data
        success = db_manager.migrate_from_json(accounts_data, groups_data)
        
        if success:
            print("✅ Data migration completed successfully!")
            return True
        else:
            print("❌ Data migration failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

def verify_migration():
    """Verify that migration was successful"""
    print("🔍 Verifying migration...")
    
    try:
        # Use project root data directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data')
        db_path = os.path.join(data_dir, "bot_database.db")
        db_manager = DatabaseManager(db_path)
        
        # Check accounts
        accounts = db_manager.get_all_accounts()
        print(f"✅ Found {len(accounts)} accounts in database")
        
        for account in accounts:
            print(f"  📱 {account.session_name} ({account.phone}) - {'Active' if account.is_active else 'Inactive'}")
        
        # Check groups
        groups = db_manager.get_all_groups()
        print(f"✅ Found {len(groups)} groups in database")
        
        for group in groups:
            print(f"  🏢 {group.group_name} (ID: {group.group_id}) - {'Active' if group.is_active else 'Inactive'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

def cleanup_json_files():
    """Move JSON files to backup after successful migration"""
    print("🧹 Moving JSON files to backup...")
    
    config_dir = "config"
    backup_dir = "config/backup"
    
    files_to_move = ["accounts.json", "groups.json"]
    
    for filename in files_to_move:
        src_path = os.path.join(config_dir, filename)
        backup_path = os.path.join(backup_dir, f"{filename}.migrated")
        
        if os.path.exists(src_path):
            shutil.move(src_path, backup_path)
            print(f"✅ Moved {filename} to backup")

def main():
    """Main migration function"""
    print("🚀 Starting migration from JSON files to database")
    print("="*60)
    
    try:
        # Step 1: Backup JSON files
        backup_json_files()
        print()
        
        # Step 2: Load data from JSON files
        accounts_data, groups_data = load_json_data()
        print()
        
        if not accounts_data and not groups_data:
            print("⚠️  No data found to migrate!")
            return
        
        # Step 3: Migrate to database
        if migrate_to_database(accounts_data, groups_data):
            print()
            
            # Step 4: Verify migration
            if verify_migration():
                print()
                
                # Step 5: Cleanup JSON files
                response = input("Migration successful! Move JSON files to backup? (y/n): ").lower().strip()
                if response in ['y', 'yes']:
                    cleanup_json_files()
                    print("\n✅ Migration completed successfully!")
                    print("📝 JSON files have been moved to config/backup/")
                else:
                    print("\n✅ Migration completed! JSON files left in place.")
            else:
                print("\n❌ Migration verification failed!")
        else:
            print("\n❌ Migration failed!")
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()