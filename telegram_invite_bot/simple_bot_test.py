#!/usr/bin/env python3
"""
Простая версия бота без Pyrogram для тестирования команд
"""
import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SimpleBotTest:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("BOT_TOKEN not found in environment variables")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        await update.message.reply_text(
            "🤖 Simple bot test is running!\n\n"
            "Available commands:\n"
            "/start - This message\n"
            "/test_groups_info - Test groups info without Pyrogram"
        )
    
    async def test_groups_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test groups info command without Pyrogram functionality"""
        try:
            # Simulate groups info text generation
            groups_info_text = """🏢 Groups Information (Test Mode)

✅ Group1 (ID: -4830144475)
   👥 Members: Test Mode - No Pyrogram
   🔗 Link: https://t.me/+zMSu-BfoKPtjNDIy

✅ Group2 (ID: -4839166945)  
   👥 Members: Test Mode - No Pyrogram
   🔗 Link: https://t.me/+XObB_XWoSGc1ZTNi

✅ Group3 (ID: -4655670337)
   👥 Members: Test Mode - No Pyrogram
   🔗 Link: https://t.me/+ASh8IBV1S0w5YzBi

📈 Update Summary:
• ✅ Successfully updated: 0 groups (Test Mode)
• ❌ Failed to update: 0 groups  
• 📊 Total groups: 3"""

            # Send without Markdown parsing
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=groups_info_text
            )
            
            logger.info("Successfully sent test groups info")
            
        except Exception as e:
            logger.error(f"Error in test_groups_info_command: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
    
    def run(self):
        """Run the bot"""
        # Create application
        application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("test_groups_info", self.test_groups_info_command))
        
        logger.info("🚀 Simple bot test starting...")
        
        # Start the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        bot = SimpleBotTest()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")