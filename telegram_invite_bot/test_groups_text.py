#!/usr/bin/env python3
"""
Простой тест для проверки команды groups_info без Markdown проблем
"""
import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import ConfigManager
from src.group_manager import GroupManager
from src.account_manager import AccountManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_groups_info_text():
    """Тест генерации текста команды groups_info"""
    print("🔧 Тестирование генерации текста groups_info...")
    
    config_manager = ConfigManager()
    group_manager = GroupManager(config_manager)
    account_manager = AccountManager(config_manager)
    
    try:
        # Initialize managers
        group_manager.initialize()
        await account_manager.initialize()
        
        print("✅ Менеджеры инициализированы")
        
        # Update member counts for all groups (this might fail, but we test text generation)
        update_results = await group_manager.update_all_groups_member_count(account_manager)
        
        # Get updated group statistics
        group_stats = group_manager.get_group_stats()
        
        # Generate text like in the command
        text = "🏢 Groups Information (Updated)\n\n"
        
        for group in group_stats['groups_details']:
            group_id = group['group_id']
            member_count = group.get('member_count', 0)
            last_updated = group.get('last_updated', 0)
            
            # Format member count
            member_text = f"{member_count}" if member_count > 0 else "Unknown"
            
            # Format last updated
            updated_text = ""
            if last_updated > 0:
                from datetime import datetime
                updated_date = datetime.fromtimestamp(last_updated)
                updated_text = f" (updated: {updated_date.strftime('%Y-%m-%d %H:%M')})"
            
            status = "✅" if group['is_active'] else "❌"
            text += f"{status} {group['group_name']} (ID: {group_id})\n"
            text += f"   👥 Members: {member_text}{updated_text}\n"
            text += f"   🔗 Link: {group.get('invite_link', 'N/A')}\n\n"
        
        # Add update summary
        text += f"📈 Update Summary:\n"
        text += f"• ✅ Successfully updated: {update_results['updated']} groups\n"
        text += f"• ❌ Failed to update: {update_results['failed']} groups\n"
        text += f"• 📊 Total groups: {len(group_stats['groups_details'])}"
        
        print("\n📄 Сгенерированный текст:")
        print("=" * 50)
        print(text)
        print("=" * 50)
        print(f"\n📊 Длина текста: {len(text)} символов")
        print("✅ Тест генерации текста завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await account_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_groups_info_text())