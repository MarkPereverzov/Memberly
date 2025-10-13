#!/usr/bin/env python3
"""
Management script for the invitation bot
"""
import os
import sys
import asyncio
import json
from pathlib import Path

# Add path to project
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import ConfigManager

def setup_project():
    """Initial project setup"""
    print("🛠 Setting up project...")
    
    # Create necessary directories
    directories = ["logs", "data", "data/sessions", "config"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Check for configuration files
    config_files = {
        ".env": ".env.example",
        "config/accounts.json": "config/accounts.json.example",
        "config/groups.json": "config/groups.json.example"
    }
    
    for target, source in config_files.items():
        if not os.path.exists(target) and os.path.exists(source):
            import shutil
            shutil.copy(source, target)
            print(f"✅ Copied configuration file: {target}")
        elif not os.path.exists(target):
            print(f"⚠️  File not found: {target}")
    
    print("\n📝 Don't forget to edit configuration files:")
    print("   - .env (bot token, user IDs)")
    print("   - config/accounts.json (user accounts)")
    print("   - config/groups.json (target groups)")

def check_config():
    """Configuration check"""
    print("🔍 Checking configuration...")
    
    # Check .env file
    if not os.path.exists(".env"):
        print("❌ .env file not found")
        return False
    
    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["BOT_TOKEN", "ADMIN_USER_IDS", "WHITELIST_USER_IDS"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check configuration files
    try:
        config_manager = ConfigManager()
        accounts = config_manager.load_accounts()
        groups = config_manager.load_groups()
        
        print(f"✅ Loaded accounts: {len(accounts)}")
        print(f"✅ Loaded groups: {len(groups)}")
        
        if not accounts:
            print("⚠️  No accounts configured")
        
        if not groups:
            print("⚠️  No groups configured")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration loading error: {e}")
        return False

def add_account():
    """Add new account"""
    print("➕ Adding new account...")
    
    try:
        session_name = input("Enter session name: ").strip()
        api_id = int(input("Enter API ID: ").strip())
        api_hash = input("Enter API Hash: ").strip()
        phone = input("Enter phone number: ").strip()
        
        config_manager = ConfigManager()
        account = config_manager.add_account(session_name, api_id, api_hash, phone)
        
        print(f"✅ Account {session_name} added successfully")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def add_group():
    """Add new group"""
    print("➕ Adding new group...")
    
    try:
        group_id = int(input("Enter group ID (example: -1001234567890): ").strip())
        group_name = input("Enter group name: ").strip()
        invite_link = input("Enter invite link: ").strip()
        
        config_manager = ConfigManager()
        group = config_manager.add_group(group_id, group_name, invite_link)
        
        print(f"✅ Group {group_name} added successfully")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def show_stats():
    """Show statistics"""
    print("📊 Configuration statistics...")
    
    try:
        config_manager = ConfigManager()
        accounts = config_manager.load_accounts()
        groups = config_manager.load_groups()
        
        print(f"\n📱 Accounts ({len(accounts)}):")
        for account in accounts:
            status = "✅" if account.is_active else "❌"
            print(f"  {status} {account.session_name} ({account.phone})")
        
        print(f"\n🏢 Groups ({len(groups)}):")
        for group in groups:
            status = "✅" if group.is_active else "❌"
            print(f"  {status} {group.group_name} (ID: {group.group_id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_accounts():
    """Test account connections"""
    print("🧪 Testing accounts...")
    
    try:
        from src.account_manager import AccountManager
        
        config_manager = ConfigManager()
        account_manager = AccountManager(config_manager)
        
        await account_manager.initialize()
        
        print("✅ All accounts tested")
        
        await account_manager.shutdown()
        
    except Exception as e:
        print(f"❌ Testing error: {e}")

def run_bot():
    """Start bot"""
    print("🚀 Starting bot...")
    
    # Check configuration before starting
    if not check_config():
        print("❌ Configuration is incorrect. Fix errors and try again.")
        return
    
    # Start main script
    os.system("python main.py")

def main():
    """Main menu"""
    while True:
        print("\n" + "="*50)
        print("🤖 Telegram Invite Bot - Management")
        print("="*50)
        print("1. 🛠  Initial setup")
        print("2. 🔍 Check configuration")
        print("3. ➕ Add account")
        print("4. ➕ Add group")
        print("5. 📊 Show statistics")
        print("6. 🧪 Test accounts")
        print("7. 🚀 Start bot")
        print("8. 🚪 Exit")
        print("="*50)
        
        choice = input("Choose action (1-8): ").strip()
        
        if choice == "1":
            setup_project()
        elif choice == "2":
            check_config()
        elif choice == "3":
            add_account()
        elif choice == "4":
            add_group()
        elif choice == "5":
            show_stats()
        elif choice == "6":
            asyncio.run(test_accounts())
        elif choice == "7":
            run_bot()
        elif choice == "8":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()