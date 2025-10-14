#!/usr/bin/env python3
"""
Test the updated join_groups command formatting
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

async def test_join_groups_formatting():
    """Test the new join_groups formatting"""
    print("🔧 Testing join_groups formatting...")
    
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
        
        # Get active groups
        active_groups = group_manager.get_active_groups()
        print(f"📊 Found {len(active_groups)} active groups")
        
        # Simulate results (like the real command would get)
        simulated_results = {}
        
        for group in active_groups:
            # Simulate successful join for all groups
            simulated_results[group.group_name] = {
                "success": ["Account 1"],  # Simulate one successful account
                "failed": []
            }
        
        # Format message like the updated command
        response_lines = ["🔄 Auto-join (Updated)\n"]
        
        total_success_groups = 0
        total_failed_groups = 0
        
        # Process each group
        for group_name, group_results in simulated_results.items():
            success_count = len(group_results["success"])
            failed_count = len(group_results["failed"])
            
            # Find group ID
            group_id = "Unknown"
            for group in active_groups:
                if group.group_name == group_name:
                    group_id = group.group_id
                    break
            
            # Determine group status - success if at least one account joined
            if success_count > 0:
                status_icon = "✅"
                total_success_groups += 1
            else:
                status_icon = "❌"
                total_failed_groups += 1
            
            response_lines.append(f"{status_icon} {group_name} (ID: {group_id})")
        
        # Add summary
        response_lines.append("")
        response_lines.append("📈 Update Summary:")
        response_lines.append(f"• ✅ Successfully: {total_success_groups} groups")
        response_lines.append(f"• ❌ Failed: {total_failed_groups} groups")
        response_lines.append(f"• 📊 Total: {len(active_groups)} groups")
        
        response_text = "\n".join(response_lines)
        
        print("\n" + "="*50)
        print("PREVIEW OF NEW /join_groups OUTPUT:")
        print("="*50)
        print(response_text)
        print("="*50)
        
        print(f"\n📊 Text length: {len(response_text)} characters")
        print("✅ Test completed!")
        
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
    asyncio.run(test_join_groups_formatting())