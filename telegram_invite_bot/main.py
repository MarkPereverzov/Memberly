"""
Main invite bot
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

from config.config import ConfigManager, BotConfig
from src.account_manager import AccountManager
from src.group_manager import GroupManager
from src.cooldown_manager import CooldownManager

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'bot.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InviteBot:
    """Main invite bot class"""
    
    def __init__(self):
        # Get script directory for correct paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, 'config')
        
        self.config_manager = ConfigManager(config_dir)
        self.account_manager = AccountManager(self.config_manager)
        self.group_manager = GroupManager(self.config_manager)
        self.cooldown_manager = CooldownManager()
        
        self.bot_config = self.config_manager.bot_config
        self.application = None
        
    async def initialize(self):
        """Bot initialization"""
        logger.info("Initializing bot...")
        
        # Initialize managers
        await self.account_manager.initialize()
        self.group_manager.initialize()
        
        # Create bot application
        self.application = Application.builder().token(self.bot_config.bot_token).build()
        
        # Register handlers
        self._register_handlers()
        
        logger.info("Bot initialized successfully")
    
    def _register_handlers(self):
        """Register command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("block", self.block_user_command))
        self.application.add_handler(CommandHandler("unblock", self.unblock_user_command))
        self.application.add_handler(CommandHandler("reset", self.reset_stats_command))
        
        # Callback button handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator"""
        return user_id in self.bot_config.admin_user_ids
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        return user_id in self.bot_config.whitelist_user_ids or self._is_admin(user_id)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot")
        
        welcome_text = f"""
🤖 **Welcome to the Invite Bot!**

Hello, {user.first_name}! 

This bot will help you get invitations to our groups.

**Available commands:**
• /invite - Get an invitation to a group
• /status - Check your status
• /help - Help

To get an invitation, use the /invite command
        """
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /invite command"""
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"Invitation request from user {user_id} ({user.username})")
        
        # Check if user is whitelisted
        if not self._is_whitelisted(user_id):
            await update.message.reply_text(
                "❌ You don't have access to this bot. Contact the administrator."
            )
            return
        
        # Check user cooldown
        can_invite, cooldown_message = self.cooldown_manager.can_user_request_invite(user_id)
        if not can_invite:
            await update.message.reply_text(f"⏰ {cooldown_message}")
            return
        
        # Get available groups
        available_groups = self.group_manager.get_available_groups_for_user(user_id)
        if not available_groups:
            await update.message.reply_text(
                "😔 Sorry, there are no available groups for invitation right now. Please try again later."
            )
            return
        
        # Select the best group
        target_group = self.group_manager.select_best_group_for_user(user_id)
        if not target_group:
            await update.message.reply_text(
                "😔 Could not find a suitable group. Please try again later."
            )
            return
        
        # Check group cooldown
        can_invite_group, group_message = self.cooldown_manager.can_invite_to_group(target_group.group_id)
        if not can_invite_group:
            await update.message.reply_text(f"⏰ {group_message}")
            return
        
        # Get available account
        account = self.account_manager.get_available_account(target_group.group_id)
        if not account:
            await update.message.reply_text(
                "😔 No available accounts to send invitation right now. Please try again later."
            )
            return
        
        # Send invitation
        await update.message.reply_text("🔄 Sending invitation...")
        
        success = await self.account_manager.send_invite(
            account, user_id, target_group.invite_link
        )
        
        if success:
            # Record successful invitation
            self.cooldown_manager.record_invite_attempt(user_id, target_group.group_id, True)
            self.group_manager.record_invitation(user_id, target_group.group_id)
            
            await update.message.reply_text(
                f"✅ **Invitation sent!**\\n\\n"
                f"Group: {target_group.group_name}\\n"
                f"Link: {target_group.invite_link}\\n\\n"
                f"Check your private messages to receive the invitation.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Invitation successfully sent to user {user_id}")
        else:
            # Record failed attempt
            self.cooldown_manager.record_invite_attempt(user_id, target_group.group_id, False)
            
            await update.message.reply_text(
                "❌ Failed to send invitation. Please try again later."
            )
            
            logger.error(f"Failed to send invitation to user {user_id}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command"""
        user_id = update.effective_user.id
        
        if not self._is_whitelisted(user_id):
            await update.message.reply_text("❌ You don't have access to this bot.")
            return
        
        # Get user statistics
        user_stats = self.cooldown_manager.get_user_stats(user_id)
        
        status_text = f"""
📊 **Your Status**

🎫 Invitations today: {user_stats['invite_count_today']}/{self.cooldown_manager.max_invites_per_day}
🎯 Remaining invitations: {user_stats['remaining_invites']}

{"🚫 Blocked" if user_stats['is_blocked'] else "✅ Active"}

{"⏰ Can request invitation" if user_stats['can_invite'] else "⏳ Waiting for cooldown"}
        """
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /stats command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Get statistics
        cooldown_stats = self.cooldown_manager.get_global_stats()
        account_stats = self.account_manager.get_account_stats()
        group_stats = self.group_manager.get_group_stats()
        
        stats_text = f"""
📈 **Bot Statistics**

**Users:**
👥 Total users: {cooldown_stats['total_users']}
🚫 Blocked: {cooldown_stats['active_blocks']}
🎫 Invitations today: {cooldown_stats['total_invites_today']}

**Accounts:**
👤 Total accounts: {account_stats['total_accounts']}
✅ Active: {account_stats['active_accounts']}
📤 Invitations from accounts: {account_stats['total_daily_invites']}

**Groups:**
🏢 Total groups: {group_stats['total_groups']}
✅ Active: {group_stats['active_groups']}
📥 Invitations to groups: {group_stats['total_daily_invites']}
        """
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        help_text = """
🆘 **Help**

**Basic Commands:**
• /start - Welcome message
• /invite - Get an invitation to a group
• /status - Check your status
• /help - This help

**How to get an invitation:**
1. Use the /invite command
2. Wait for request processing
3. Check your private messages

**Limitations:**
• Maximum 10 invitations per day
• 5-minute break between invitations
• Only available to whitelisted users

For questions, contact the administrator.
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /admin command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
                InlineKeyboardButton("👥 Accounts", callback_data="admin_accounts")
            ],
            [
                InlineKeyboardButton("🏢 Groups", callback_data="admin_groups"),
                InlineKeyboardButton("⏰ Cooldowns", callback_data="admin_cooldowns")
            ],
            [
                InlineKeyboardButton("🔄 Reset Statistics", callback_data="admin_reset"),
                InlineKeyboardButton("🧹 Cleanup", callback_data="admin_cleanup")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 **Admin Panel**\\n\\nSelect an action:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def block_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /block command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /block <user_id> [hours]")
            return
        
        try:
            user_id = int(context.args[0])
            hours = int(context.args[1]) if len(context.args) > 1 else 24
            
            self.cooldown_manager.block_user(user_id, hours)
            await update.message.reply_text(f"✅ User {user_id} blocked for {hours} hours.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use numbers.")
    
    async def unblock_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /unblock command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unblock <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            self.cooldown_manager.unblock_user(user_id)
            await update.message.reply_text(f"✅ User {user_id} unblocked.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def reset_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /reset command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        self.cooldown_manager.reset_daily_stats()
        self.account_manager.reset_daily_stats()
        self.group_manager.reset_daily_stats()
        
        await update.message.reply_text("✅ Daily statistics reset.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Button click handler"""
        query = update.callback_query
        await query.answer()
        
        if not self._is_admin(query.from_user.id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        if query.data == "admin_stats":
            await self._show_detailed_stats(query)
        elif query.data == "admin_accounts":
            await self._show_account_details(query)
        elif query.data == "admin_groups":
            await self._show_group_details(query)
        elif query.data == "admin_cooldowns":
            await self._show_cooldown_details(query)
        elif query.data == "admin_reset":
            await self._confirm_reset(query)
        elif query.data == "admin_cleanup":
            await self._perform_cleanup(query)
    
    async def _show_detailed_stats(self, query):
        """Show detailed statistics"""
        recent_activity = self.cooldown_manager.get_recent_activity(24)
        
        stats_text = "📊 **Detailed Statistics (24 hours)**\\n\\n"
        
        if recent_activity:
            stats_text += "**Active Users:**\\n"
            for activity in recent_activity[:10]:  # Show only first 10
                last_time = datetime.fromtimestamp(activity['last_invite_time'])
                stats_text += f"• {activity['user_id']}: {activity['invite_count_today']} invitations, last: {last_time.strftime('%H:%M')}\\n"
        else:
            stats_text += "No activity."
        
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_account_details(self, query):
        """Show account details"""
        account_stats = self.account_manager.get_account_stats()
        
        details_text = "👤 **Account Status**\\n\\n"
        
        for account in account_stats['accounts_details']:
            status = "✅" if account['is_active'] else "❌"
            details_text += f"{status} {account['session_name']}: {account['daily_invites']} invitations\\n"
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_group_details(self, query):
        """Show group details"""
        group_stats = self.group_manager.get_group_stats()
        
        details_text = "🏢 **Group Status**\\n\\n"
        
        for group in group_stats['groups_details']:
            status = "✅" if group['is_active'] else "❌"
            details_text += f"{status} {group['group_name']}: {group['daily_invites']}/{group['max_daily_invites']}\\n"
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_cooldown_details(self, query):
        """Show cooldown details"""
        global_stats = self.cooldown_manager.get_global_stats()
        
        details_text = f"""
⏰ **Cooldown Settings**

🕐 Invitation cooldown: {global_stats['invite_cooldown_seconds']}s
🕑 Group cooldown: {global_stats['group_cooldown_seconds']}s
🎫 Max invitations per day: {global_stats['max_invites_per_day']}

👥 Total users: {global_stats['total_users']}
🚫 Blocked: {global_stats['active_blocks']}
        """
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _confirm_reset(self, query):
        """Confirm statistics reset"""
        self.cooldown_manager.reset_daily_stats()
        self.account_manager.reset_daily_stats()
        self.group_manager.reset_daily_stats()
        
        await query.edit_message_text("✅ All daily statistics have been reset.")
    
    async def _perform_cleanup(self, query):
        """Perform cleanup"""
        self.cooldown_manager.cleanup_expired_blocks()
        await query.edit_message_text("✅ Cleanup completed. Expired blocks removed.")
    
    def start_bot(self):
        """Synchronous bot startup"""
        logger.info("Starting bot...")
        
        try:
            # Initialize in separate event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.initialize())
                
                # Start polling
                self.application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def run(self):
        """Bot startup"""
        logger.info("Starting bot...")
        
        try:
            await self.initialize()
            # Use run_polling which correctly manages event loop
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def shutdown(self):
        """Bot shutdown"""
        logger.info("Shutting down bot...")
        
        try:
            if self.account_manager:
                await self.account_manager.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Bot stopped")

def main():
    """Main function"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create necessary directories
    os.makedirs(os.path.join(script_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(script_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(script_dir, "data", "sessions"), exist_ok=True)
    
    # Start bot
    bot = InviteBot()
    
    try:
        # Use run_polling which manages event loop itself
        bot.start_bot()
    except KeyboardInterrupt:
        logger.info("Stopped by user signal")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())