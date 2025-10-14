#!/usr/bin/env python3
"""
Simple test for updated member count functionality
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

async def test_member_count():
    """Test member count with invite links"""
    print("🔧 Testing member count with invite links...")
    
    try:
        # Initialize managers
        config_manager = ConfigManager()
        account_manager = AccountManager(config_manager)
        group_manager = GroupManager(config_manager)
        
        print("✅ Managers created")
        
        # Initialize
        await account_manager.initialize()
        group_manager.initialize()
        print("✅ Managers initialized")
        
        # Test single group
        groups = group_manager.get_active_groups()
        if groups:
            group = groups[0]  # Test first group
            print(f"\n🔍 Testing group: {group.group_name}")
            print(f"   Group ID: {group.group_id}")
            print(f"   Invite Link: {group.invite_link}")
            
            # Test new method with invite link
            member_count = await account_manager.get_group_member_count(group.group_id, group.invite_link)
            
            if member_count is not None:
                print(f"   ✅ Member count: {member_count}")
            else:
                print(f"   ❌ Could not get member count")
        else:
            print("❌ No active groups found")
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if 'account_manager' in locals():
            try:
                for client in account_manager.clients.values():
                    if client:
                        await client.stop()
                print("✅ Clients disconnected")
            except Exception as e:
                print(f"⚠️ Error disconnecting: {e}")

if __name__ == "__main__":
    asyncio.run(test_member_count())