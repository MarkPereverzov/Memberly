#!/usr/bin/env python3
"""
Test script to check groups_info functionality
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add path to modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import ConfigManager
from src.group_manager import GroupManager
from src.account_manager import AccountManager

load_dotenv()

async def test_groups_info():
    """Test groups info generation"""
    print("🔧 Testing groups_info functionality...")
    
    try:
        # Initialize managers
        config_manager = ConfigManager()
        account_manager = AccountManager(config_manager.load_accounts())
        group_manager = GroupManager(config_manager.load_groups(), account_manager)
        
        print("✅ Managers initialized")
        
        # Connect accounts
        await account_manager.connect_all()
        print("✅ Accounts connected")
        
        # Test groups info without member count update
        print("\n📄 Testing basic groups_info generation...")
        groups_info_text = group_manager.get_groups_info_text()
        print("Generated text:")
        print("=" * 50)
        print(groups_info_text)
        print("=" * 50)
        
        # Test with member count update
        print("\n📊 Testing groups_info with member count update...")
        updated_text = group_manager.get_groups_info_text(update_member_count=True)
        print("Updated text:")
        print("=" * 50)
        print(updated_text)
        print("=" * 50)
        
        print(f"📊 Text length: {len(updated_text)} characters")
        print("✅ groups_info test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnect accounts
        if 'account_manager' in locals():
            await account_manager.disconnect_all()
            print("✅ Accounts disconnected")

if __name__ == "__main__":
    asyncio.run(test_groups_info())