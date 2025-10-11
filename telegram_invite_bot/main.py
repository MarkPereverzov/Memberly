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
from src.database_manager import DatabaseManager
from src.whitelist_manager import WhitelistManager
from src.group_stats_collector import GroupStatsCollector

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
        data_dir = os.path.join(script_dir, '..', 'data')
        
        self.config_manager = ConfigManager(config_dir)
        self.account_manager = AccountManager(self.config_manager)
        self.group_manager = GroupManager(self.config_manager)
        self.cooldown_manager = CooldownManager()
        
        # Initialize database and whitelist managers
        db_path = os.path.join(data_dir, "bot_database.db")
        self.database_manager = DatabaseManager(db_path)
        self.whitelist_manager = WhitelistManager(
            self.database_manager, 
            self.config_manager.bot_config.admin_user_ids
        )
        
        # Initialize group statistics collector
        self.group_stats_collector = GroupStatsCollector(
            self.database_manager,
            self.group_manager,
            self.account_manager
        )
        
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
        
        # Start group statistics collection
        await self.group_stats_collector.start_collection()
        
        logger.info("Bot initialized successfully")
    
    def _register_handlers(self):
        """Register command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("whitelist", self.whitelist_command))
        self.application.add_handler(CommandHandler("remove_whitelist", self.remove_whitelist_command))
        self.application.add_handler(CommandHandler("add_group", self.add_group_command))
        self.application.add_handler(CommandHandler("remove_group", self.remove_group_command))
        self.application.add_handler(CommandHandler("groups_info", self.groups_info_command))
        self.application.add_handler(CommandHandler("force_stats", self.force_stats_command))
        self.application.add_handler(CommandHandler("block", self.block_user_command))
        self.application.add_handler(CommandHandler("unblock", self.unblock_user_command))
        self.application.add_handler(CommandHandler("reset", self.reset_stats_command))
        
        # Callback button handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator"""
        return self.whitelist_manager.is_admin(user_id)
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        return self.whitelist_manager.is_user_whitelisted(user_id)
    
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
        """Handler for /invite command - invites user to ALL groups sequentially"""
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"Invitation request from user {user_id} ({user.username})")
        
        # Check if user is whitelisted
        if not self._is_whitelisted(user_id):
            await update.message.reply_text(
                "❌ You don't have access to this bot. Contact the administrator."
            )
            return
        
        # Check user cooldown (only time-based, no daily limits)
        can_invite, cooldown_message = self.cooldown_manager.can_user_request_invite_simple(user_id)
        if not can_invite:
            await update.message.reply_text(f"⏰ {cooldown_message}")
            return
        
        # Get all active groups
        all_groups = self.group_manager.get_active_groups()
        if not all_groups:
            await update.message.reply_text(
                "😔 Sorry, there are no available groups right now."
            )
            return
        
        await update.message.reply_text(f"🔄 Starting invitations to {len(all_groups)} groups...")
        
        successful_invites = []
        failed_invites = []
        
        # Get all available accounts
        all_accounts = self.account_manager.get_active_accounts()
        if not all_accounts:
            await update.message.reply_text(
                "😔 No available accounts to send invitations right now."
            )
            return
        
        account_index = 0
        
        # Process each group
        for i, group in enumerate(all_groups):
            # Check group cooldown
            can_invite_group, group_message = self.cooldown_manager.can_invite_to_group(group.group_id)
            if not can_invite_group:
                failed_invites.append(f"{group.group_name}: {group_message}")
                continue
            
            # Get account (rotate through available accounts)
            account = all_accounts[account_index % len(all_accounts)]
            account_index += 1
            
            # Send invitation
            try:
                success = await self.account_manager.send_invite(
                    account, user_id, group.invite_link
                )
                
                if success:
                    successful_invites.append(group.group_name)
                    
                    # Record successful invitation
                    self.cooldown_manager.record_invite_attempt(user_id, group.group_id, True)
                    self.group_manager.record_invitation(user_id, group.group_id)
                    
                    # Record in database
                    self.database_manager.record_invitation(
                        user_id, group.group_id, group.group_name, True
                    )
                    
                    logger.info(f"Successfully invited user {user_id} to group {group.group_name}")
                else:
                    failed_invites.append(f"{group.group_name}: Failed to send invitation")
                    
                    # Record failed attempt
                    self.cooldown_manager.record_invite_attempt(user_id, group.group_id, False)
                    
                    # Record in database
                    self.database_manager.record_invitation(
                        user_id, group.group_id, group.group_name, False, "Failed to send invitation"
                    )
                    
            except Exception as e:
                failed_invites.append(f"{group.group_name}: Error - {str(e)}")
                logger.error(f"Error inviting user {user_id} to group {group.group_name}: {e}")
            
            # Small delay between invitations to avoid rate limiting
            if i < len(all_groups) - 1:  # Don't delay after the last invitation
                await asyncio.sleep(1)
        
        # Update user's last invite time
        self.cooldown_manager.update_user_last_invite_time(user_id)
        
        # Prepare result message
        result_message = "🎉 **Invitation Results**\n\n"
        
        if successful_invites:
            result_message += f"✅ **Successfully added to {len(successful_invites)} groups:**\n"
            for group_name in successful_invites:
                result_message += f"• {group_name}\n"
            result_message += "\n"
        
        if failed_invites:
            result_message += f"❌ **Failed to add to {len(failed_invites)} groups:**\n"
            for failure in failed_invites:
                result_message += f"• {failure}\n"
            result_message += "\n"
        
        if not successful_invites and not failed_invites:
            result_message += "😔 No invitations were processed.\n"
        
        result_message += "📩 Check your private messages for invitation links!"
        
        await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command"""
        user_id = update.effective_user.id
        
        # Get access information
        can_access, reason = self.whitelist_manager.can_user_access(user_id)
        if not can_access:
            await update.message.reply_text(f"❌ {reason}")
            return
        
        # Get user statistics
        user_stats = self.cooldown_manager.get_user_stats(user_id)
        access_info = self.whitelist_manager.get_user_access_info(user_id)
        
        status_text = f"📊 **Your Status**\n\n"
        
        # Access level
        if access_info['is_admin']:
            status_text += "👑 **Administrator**\n"
        elif access_info['is_whitelisted']:
            status_text += f"✅ **Whitelisted** ({access_info['days_remaining']} days remaining)\n"
        else:
            status_text += "❌ **Not whitelisted**\n"
        
        # Invitation statistics
        status_text += f"\n🎫 **Invitations:**\n"
        status_text += f"• Today: {user_stats['invite_count_today']}/{self.cooldown_manager.max_invites_per_day}\n"
        status_text += f"• Remaining: {user_stats['remaining_invites']}\n"
        
        # Block status
        if user_stats['is_blocked']:
            block_until = datetime.fromtimestamp(user_stats['blocked_until'])
            status_text += f"\n🚫 **Blocked until:** {block_until.strftime('%H:%M %d.%m.%Y')}\n"
        else:
            status_text += f"\n✅ **Status:** Active\n"
        
        # Cooldown status
        can_invite, cooldown_msg = self.cooldown_manager.can_user_request_invite(user_id)
        if can_invite:
            status_text += "⏰ **Next invitation:** Available now\n"
        else:
            status_text += f"⏰ **Next invitation:** {cooldown_msg}\n"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        user_id = update.effective_user.id
        is_admin = self._is_admin(user_id)
        
        help_text = "🆘 Help\n\n"
        
        help_text += "Basic Commands:\n"
        help_text += "• /start - Welcome message\n"
        help_text += "• /invite - Get an invitation to a group\n"
        help_text += "• /status - Check your status\n"
        help_text += "• /groups_info - View groups information\n"
        help_text += "• /help - This help\n"
        
        if is_admin:
            help_text += "\nAdmin Commands:\n"
            help_text += "• /admin - Admin panel\n"
            help_text += "• /whitelist (user_id) (days) - Add user to whitelist\n"
            help_text += "• /remove_whitelist (user_id) - Remove from whitelist\n"
            help_text += "• /add_group (id) (name) (link) - Add group\n"
            help_text += "• /remove_group (id) - Remove group\n"
            help_text += "• /force_stats - Force statistics collection\n"
            help_text += "• /block (user_id) [hours] - Block user\n"
            help_text += "• /unblock (user_id) - Unblock user\n"
            help_text += "• /reset - Reset daily statistics\n"
        
        help_text += "\nHow to get an invitation:\n"
        help_text += "1. Use the /invite command\n"
        help_text += "2. Wait for request processing\n"
        help_text += "3. Check your private messages\n"
        
        help_text += "\nLimitations:\n"
        help_text += "• Maximum 10 invitations per day\n"
        help_text += "• 5-minute break between invitations\n"
        help_text += "• Only available to whitelisted users\n"
        
        help_text += "\nFor questions, contact the administrator."
        
        await update.message.reply_text(help_text)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /admin command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("👥 Accounts", callback_data="admin_accounts_0"),
                InlineKeyboardButton("🏢 Groups", callback_data="admin_groups_0")
            ],
            [
                InlineKeyboardButton("📊 Statistics", callback_data="admin_statistics")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 **Admin Panel**\n\nSelect section:",
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
    
    async def whitelist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /whitelist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /whitelist <user_id> <days> [username]\n"
                "Example: /whitelist 123456789 30 @username"
            )
            return
        
        try:
            user_id = int(context.args[0])
            days = int(context.args[1])
            username = context.args[2] if len(context.args) > 2 else None
            
            if days <= 0:
                await update.message.reply_text("❌ Days must be a positive number.")
                return
            
            success = self.whitelist_manager.add_to_whitelist(
                user_id, days, update.effective_user.id, username
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ User {user_id} added to whitelist for {days} days."
                )
                
                # Record in database
                self.database_manager.record_invitation(
                    user_id, 0, "Whitelist Addition", True, f"Added by admin for {days} days"
                )
            else:
                await update.message.reply_text("❌ Failed to add user to whitelist.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid format. User ID and days must be numbers.")
    
    async def remove_whitelist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /remove_whitelist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /remove_whitelist <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            
            success = self.whitelist_manager.remove_from_whitelist(user_id)
            
            if success:
                await update.message.reply_text(f"✅ User {user_id} removed from whitelist.")
            else:
                await update.message.reply_text(f"❌ User {user_id} not found in whitelist.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def add_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /add_group command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /add_group <group_id> <group_name> <invite_link> [max_daily_invites]\n"
                "Example: /add_group -1001234567890 \"Test Group\" https://t.me/+abc123 100"
            )
            return
        
        try:
            group_id = int(context.args[0])
            group_name = context.args[1]
            invite_link = context.args[2]
            max_daily_invites = int(context.args[3]) if len(context.args) > 3 else 100
            
            if not invite_link.startswith('https://t.me/'):
                await update.message.reply_text("❌ Invalid invite link. Must start with https://t.me/")
                return
            
            success = self.group_manager.add_group(group_id, group_name, invite_link, max_daily_invites)
            
            if success:
                await update.message.reply_text(f"✅ Group '{group_name}' added successfully.")
            else:
                await update.message.reply_text("❌ Failed to add group. Group may already exist.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Group ID and max invites must be numbers.")
    
    async def remove_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /remove_group command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /remove_group <group_id>")
            return
        
        try:
            group_id = int(context.args[0])
            
            success = self.group_manager.remove_group(group_id)
            
            if success:
                await update.message.reply_text(f"✅ Group with ID {group_id} removed successfully.")
            else:
                await update.message.reply_text(f"❌ Group with ID {group_id} not found.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid group ID.")
    
    async def groups_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /groups_info command"""
        user_id = update.effective_user.id
        
        # Check access
        can_access, reason = self.whitelist_manager.can_user_access(user_id)
        if not can_access:
            await update.message.reply_text(f"❌ {reason}")
            return
        
        # Get group statistics
        group_stats = self.group_manager.get_group_stats()
        db_stats = self.database_manager.get_overall_statistics()
        
        text = "🏢 **Groups Information**\n\n"
        text += f"📊 **Overall Statistics:**\n"
        text += f"• Total groups: {group_stats['total_groups']}\n"
        text += f"• Active groups: {group_stats['active_groups']}\n"
        text += f"• Daily invitations: {group_stats['total_daily_invites']}\n"
        
        if db_stats:
            text += f"• Average members: {int(db_stats.get('average_member_count', 0))}\n"
            largest = db_stats.get('largest_group', {})
            if largest.get('name') != 'N/A':
                text += f"• Largest group: {largest['name']} ({largest['member_count']} members)\n"
        
        text += f"\n📋 **Group Details:**\n"
        
        for group in group_stats['groups_details'][:10]:  # Show first 10 groups
            status = "✅" if group['is_active'] else "❌"
            text += f"{status} {group['group_name']}\n"
            text += f"   📈 {group['daily_invites']}/{group['max_daily_invites']} invitations today\n"
        
        if len(group_stats['groups_details']) > 10:
            text += f"\n... and {len(group_stats['groups_details']) - 10} more groups"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def force_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /force_stats command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        await update.message.reply_text("🔄 Collecting group statistics...")
        
        try:
            results = await self.group_stats_collector.force_collection()
            
            text = f"📊 **Statistics Collection Results**\n\n"
            text += f"📋 Total groups: {results['total_groups']}\n"
            text += f"✅ Successful: {results['successful']}\n"
            text += f"❌ Failed: {results['failed']}\n"
            
            if results['errors']:
                text += f"\n⚠️ **Errors:**\n"
                for error in results['errors'][:5]:  # Show first 5 errors
                    text += f"• {error}\n"
                
                if len(results['errors']) > 5:
                    text += f"... and {len(results['errors']) - 5} more errors"
            
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error during statistics collection: {str(e)}")
            logger.error(f"Error in force_stats_command: {e}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Button click handler"""
        query = update.callback_query
        await query.answer()
        
        if not self._is_admin(query.from_user.id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        if query.data.startswith("admin_accounts_"):
            page = int(query.data.split("_")[-1])
            await self._show_accounts_page(query, page)
        elif query.data.startswith("admin_groups_"):
            page = int(query.data.split("_")[-1])
            await self._show_groups_page(query, page)
        elif query.data == "admin_statistics":
            await self._show_statistics(query)
        elif query.data == "admin_back":
            await self._show_admin_menu(query)
    
    async def _show_accounts_page(self, query, page=0):
        """Show accounts with pagination"""
        account_stats = self.account_manager.get_account_stats()
        accounts = account_stats.get('accounts_details', [])
        
        # Calculate pagination
        items_per_page = 15
        total_items = len(accounts)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_accounts = accounts[start_idx:end_idx]
        
        # Build message text
        text = f"👥 **Accounts** (Page {page + 1}/{total_pages})\n\n"
        
        if not page_accounts:
            text += "No accounts found."
        else:
            for account in page_accounts:
                daily_invites = account.get('daily_invites', 0)
                text += f"• {account['session_name']} - {daily_invites} invitations\n"
        
        # Build pagination keyboard
        keyboard = []
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_accounts_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_accounts_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_groups_page(self, query, page=0):
        """Show groups with pagination"""
        group_stats = self.group_manager.get_group_stats()
        groups = group_stats.get('groups_details', [])
        
        # Calculate pagination
        items_per_page = 15
        total_items = len(groups)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_groups = groups[start_idx:end_idx]
        
        # Build message text
        text = f"🏢 **Groups** (Page {page + 1}/{total_pages})\n\n"
        
        if not page_groups:
            text += "No groups found."
        else:
            for group in page_groups:
                daily_invites = group.get('daily_invites', 0)
                text += f"• {group['group_name']} - {daily_invites} invitations\n"
        
        # Build pagination keyboard
        keyboard = []
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_groups_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_groups_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_admin_menu(self, query):
        """Show main admin menu"""
        keyboard = [
            [
                InlineKeyboardButton("👥 Accounts", callback_data="admin_accounts_0"),
                InlineKeyboardButton("🏢 Groups", callback_data="admin_groups_0")
            ],
            [
                InlineKeyboardButton("📊 Statistics", callback_data="admin_statistics")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔧 **Admin Panel**\n\nSelect section:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def _show_statistics(self, query):
        """Show bot statistics"""
        # Get statistics
        cooldown_stats = self.cooldown_manager.get_global_stats()
        account_stats = self.account_manager.get_account_stats()
        group_stats = self.group_manager.get_group_stats()
        db_stats = self.database_manager.get_overall_statistics()
        whitelist_stats = self.whitelist_manager.get_whitelist_stats()
        
        stats_text = f"📈 **Bot Statistics**\n\n"
        
        stats_text += f"**Users:**\n"
        stats_text += f"👥 Total users: {cooldown_stats['total_users']}\n"
        stats_text += f"✅ Active whitelisted: {whitelist_stats['active_users']}\n"
        stats_text += f"� Administrators: {whitelist_stats['total_admins']}\n"
        stats_text += f"�🚫 Blocked: {cooldown_stats['active_blocks']}\n"
        
        stats_text += f"\n**Invitations (Last 30 days):**\n"
        stats_text += f"📤 Total: {db_stats.get('total_invitations_30d', 0)}\n"
        stats_text += f"✅ Successful: {db_stats.get('successful_invitations_30d', 0)}\n"
        stats_text += f"📊 Success rate: {db_stats.get('success_rate_30d', 0)}%\n"
        stats_text += f"🎫 Today: {cooldown_stats['total_invites_today']}\n"
        
        stats_text += f"\n**Accounts:**\n"
        stats_text += f"👤 Total: {account_stats['total_accounts']}\n"
        stats_text += f"✅ Active: {account_stats['active_accounts']}\n"
        stats_text += f"📤 Daily invites: {account_stats['total_daily_invites']}\n"
        
        stats_text += f"\n**Groups:**\n"
        stats_text += f"🏢 Total: {group_stats['total_groups']}\n"
        stats_text += f"✅ Active: {group_stats['active_groups']}\n"
        stats_text += f"� Avg members: {int(db_stats.get('average_member_count', 0))}\n"
        
        largest_group = db_stats.get('largest_group', {})
        if largest_group.get('name') != 'N/A':
            stats_text += f"🏆 Largest: {largest_group['name']} ({largest_group['member_count']} members)\n"
        
        # Add back button
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
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
            
            # Stop group statistics collection
            if self.group_stats_collector:
                await self.group_stats_collector.stop_collection()
                
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