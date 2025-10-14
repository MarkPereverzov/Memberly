#!/usr/bin/env python3
"""
Script to reset bot state and clear webhook/polling conflicts
"""
import os
import asyncio
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def reset_bot_webhook():
    """Reset bot webhook to clear any conflicts"""
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ BOT_TOKEN not found in environment variables")
        return False
    
    # Delete webhook to clear any conflicts
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    try:
        data = json.dumps({"drop_pending_updates": True}).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    print("✅ Successfully deleted webhook and cleared pending updates")
                    return True
                else:
                    print(f"❌ Failed to delete webhook: {result.get('description')}")
            else:
                print(f"❌ HTTP error: {response.status}")
    except Exception as e:
        print(f"❌ Error resetting webhook: {e}")
    
    return False

def get_bot_info():
    """Get bot information"""
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        return None
    
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    bot_info = result.get('result', {})
                    print(f"🤖 Bot info: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                    return bot_info
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
    
    return None

if __name__ == "__main__":
    print("🔧 Resetting bot state...")
    
    # Get bot info first
    bot_info = get_bot_info()
    if not bot_info:
        print("❌ Could not get bot info")
        exit(1)
    
    # Reset webhook
    if reset_bot_webhook():
        print("✅ Bot state reset successfully")
        print("📱 Bot is ready for polling mode")
    else:
        print("❌ Failed to reset bot state")
        exit(1)