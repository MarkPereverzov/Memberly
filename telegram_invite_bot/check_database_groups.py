#!/usr/bin/env python3
"""
Check groups in database
"""
import os
import sys
from dotenv import load_dotenv

# Add path to modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import ConfigManager

load_dotenv()

def check_database_groups():
    """Check what groups are in the database"""
    print("🔧 Checking groups in database...")
    
    try:
        # Initialize config manager
        config_manager = ConfigManager()
        groups = config_manager.load_groups()
        
        print(f"📊 Found {len(groups)} groups in database:")
        print("=" * 60)
        
        for i, group in enumerate(groups, 1):
            print(f"{i}. Group Name: {group.group_name}")
            print(f"   Group ID: {group.group_id}")
            print(f"   Invite Link: {group.invite_link}")
            print(f"   Is Active: {group.is_active}")
            print(f"   Assigned Accounts: {group.assigned_accounts}")
            print(f"   Member Count: {getattr(group, 'member_count', 'N/A')}")
            print("-" * 40)
        
        # Also check database directly
        print("\n🗄️ Checking database directly...")
        db_groups = config_manager.db.get_all_groups()
        
        for group in db_groups:
            print(f"DB Group: {group.group_name} - ID: {group.group_id}")
            print(f"  Link: {group.invite_link}")
            
        print("✅ Database check completed!")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database_groups()