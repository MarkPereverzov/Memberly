#!/usr/bin/env python3
"""
Debug script to test group member count access
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add path to modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import ConfigManager
from src.account_manager import AccountManager

load_dotenv()

async def debug_group_access():
    """Debug group access and member count"""
    print("🔧 Debugging group access...")
    
    try:
        # Initialize managers
        config_manager = ConfigManager()
        accounts = config_manager.load_accounts()
        account_manager = AccountManager(config_manager)
        
        print("✅ Managers initialized")
        
        # Connect accounts
        await account_manager.initialize()
        print("✅ Accounts connected")
        
        # Test groups
        test_groups = [
            (-4830144475, "Group1"),
            (-4839166945, "Group2"), 
            (-4655670337, "Group3")
        ]
        
        for group_id, group_name in test_groups:
            print(f"\n🔍 Testing group {group_name} (ID: {group_id})")
            
            # Get the first available client
            active_accounts = [acc for acc in account_manager.accounts if acc.is_active]
            if not active_accounts:
                print("❌ No active accounts found")
                continue
                
            account = active_accounts[0]
            client = account_manager.clients.get(account.session_name)
            
            if not client:
                print(f"❌ No client for account {account.session_name}")
                continue
                
            try:
                # Test basic chat access
                print(f"   📡 Getting chat info...")
                chat = await client.get_chat(group_id)
                print(f"   ✅ Chat title: {getattr(chat, 'title', 'Unknown')}")
                print(f"   📊 Chat type: {getattr(chat, 'type', 'Unknown')}")
                print(f"   👥 Members count: {getattr(chat, 'members_count', 'Unknown')}")
                
                # Test membership status
                print(f"   👤 Checking membership status...")
                me = await client.get_me()
                member = await client.get_chat_member(group_id, me.id)
                print(f"   ✅ Member status: {member.status}")
                
                # Test permissions
                print(f"   🔐 User info: {me.first_name} (@{me.username}) ID: {me.id}")
                
                # Try to get member count using different methods
                if hasattr(chat, 'members_count') and chat.members_count is not None:
                    print(f"   ✅ Member count available: {chat.members_count}")
                else:
                    print(f"   ❌ Member count not available")
                    
                    # Try to get full chat info
                    try:
                        full_chat = await client.get_chat(group_id)
                        print(f"   📝 Full chat attributes: {dir(full_chat)}")
                    except Exception as e:
                        print(f"   ❌ Could not get full chat: {e}")
                
            except Exception as e:
                print(f"   ❌ Error testing group {group_name}: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n✅ Debug completed!")
        
    except Exception as e:
        print(f"❌ Error in debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnect accounts
        if 'account_manager' in locals():
            try:
                for client in account_manager.clients.values():
                    if client:
                        await client.stop()
                print("✅ Accounts disconnected")
            except Exception as e:
                print(f"⚠️ Error disconnecting: {e}")

if __name__ == "__main__":
    asyncio.run(debug_group_access())