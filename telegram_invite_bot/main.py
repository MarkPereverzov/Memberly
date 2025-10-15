"""
Main invite bot
"""
import asyncio
import logging
import os
import sys
import time
from typing import Dict, List

# Add path to modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config.config import ConfigManager, BotConfig
from src.account_manager import AccountManager
from src.group_manager import GroupManager
from src.cooldown_manager import CooldownManager
from src.database_manager import DatabaseManager
from src.whitelist_manager import WhitelistManager
from src.blacklist_manager import BlacklistManager
from src.group_stats_collector import GroupStatsCollector

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING,
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'bot.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Setup logging levels for important components
logging.getLogger('src.account_manager').setLevel(logging.INFO)
logging.getLogger('src.group_manager').setLevel(logging.INFO)
logging.getLogger('src.cooldown_manager').setLevel(logging.ERROR)
logging.getLogger('src.database_manager').setLevel(logging.ERROR)
logging.getLogger('src.group_stats_collector').setLevel(logging.ERROR)
logging.getLogger('__main__').setLevel(logging.ERROR)

# Disable logs from external libraries
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('telegram').setLevel(logging.ERROR)
logging.getLogger('pyrogram').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

class InviteBot:
    """Main invite bot class"""
    
    def __init__(self):
        # Get script directory for correct paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, 'config')
        data_dir = os.path.join(script_dir, 'data')
        
        self.config_manager = ConfigManager(config_dir)
        self.account_manager = AccountManager(self.config_manager)
        self.group_manager = GroupManager(self.config_manager)
        self.cooldown_manager = CooldownManager(config=self.config_manager.bot_config)
        
        # Initialize database and whitelist managers - use telegram_invite_bot/data
        db_path = os.path.join(data_dir, "bot_database.db")
        self.database_manager = DatabaseManager(db_path)
        self.whitelist_manager = WhitelistManager(
            self.database_manager, 
            self.config_manager.bot_config.admin_user_ids
        )
        self.blacklist_manager = BlacklistManager(self.database_manager)
        
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
        
        # Initialize managers
        await self.account_manager.initialize()
        self.group_manager.initialize()
        
        # Create bot application
        self.application = Application.builder().token(self.bot_config.bot_token).build()
        
        # Register handlers
        self._register_handlers()
        
        # Note: Automatic group statistics collection disabled
        # Statistics are collected on-demand via /groups_info command
        # await self.group_stats_collector.start_collection()
        
    
    def _register_handlers(self):
        """Register command handlers"""
        # User commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Admin commands - Group & Account Management
        self.application.add_handler(CommandHandler("groups_info", self.groups_info_command))
        self.application.add_handler(CommandHandler("accounts_info", self.accounts_info_command))
        self.application.add_handler(CommandHandler("add_group", self.add_group_command))
        self.application.add_handler(CommandHandler("remove_group", self.remove_group_command))
        self.application.add_handler(CommandHandler("join_groups", self.join_groups_command))
        
        # Admin commands - User Management
        self.application.add_handler(CommandHandler("whitelist", self.whitelist_command))
        self.application.add_handler(CommandHandler("remove_whitelist", self.remove_whitelist_command))
        self.application.add_handler(CommandHandler("blacklist", self.blacklist_command))
        self.application.add_handler(CommandHandler("unblacklist", self.unblacklist_command))
        self.application.add_handler(CommandHandler("blacklist_info", self.blacklist_info_command))
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator"""
        return self.whitelist_manager.is_admin(user_id)
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        return self.whitelist_manager.is_user_whitelisted(user_id)
    
    def _update_user_info(self, user) -> None:
        """Update user information in database"""
        if user:
            self.database_manager.update_user_info(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        # Update user info in database
        self._update_user_info(update.effective_user)
        
        user = update.effective_user
        
        welcome_text = f"""
🤖 **Welcome to the Invite Bot!**

Hello, {user.first_name}! 

This bot will help you get invitations to our groups.

**📋 Main Commands:**
• `/invite` - Get invitations to all groups
• `/status` - Check your status
• `/help` - Complete command reference

To get an invitation, use the `/invite` command
        """
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /invite command - invites user to ALL groups sequentially"""
        user = update.effective_user
        user_id = user.id
        
        # Check if user is blacklisted first
        if self.blacklist_manager.is_user_blocked(user_id):
            blacklist_entry = self.blacklist_manager.get_user_info(user_id)
            reason = blacklist_entry.reason if blacklist_entry else "No reason specified"
            await update.message.reply_text(
                f"🚫 You are blocked from using this bot.\n"
                f"**Reason:** {reason}\n\n"
                f"Contact an administrator if you believe this is an error."
            )
            return
        
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
        
        await update.message.reply_text(f"🔄 Starting invitations to {len(all_groups)} groups...\n💡 First, attempting to establish contact for better success rates.")
        
        successful_invites = []  # Successfully added to groups
        already_member = []      # Already in group  
        failed_invites = []      # Failed to add (need privacy settings change)
        contact_messages_sent = [] # Groups where contact message was sent
        
        # Get all available accounts
        all_accounts = self.account_manager.get_active_accounts()
        if not all_accounts:
            await update.message.reply_text(
                "😔 No available accounts to send invitations right now."
            )
            return
        
        # First, check if we can reach the user at all
        primary_account = all_accounts[0]  # Use first account for contact establishment
        can_reach_user = False
        bot_account_info = ""
        
        # Get bot account information
        try:
            bot_info_success, bot_account_info = await self.account_manager.get_bot_info(primary_account)
            if not bot_info_success:
                bot_account_info = "our bot account"
        except Exception:
            bot_account_info = "our bot account"
        
        # Try a more aggressive contact establishment approach
        try:
            # First attempt: normal add_user_to_contacts
            contact_success, contact_msg = await self.account_manager.add_user_to_contacts(primary_account, user_id)
            if contact_success:
                can_reach_user = True
                logger.info(f"User {user_id} is reachable: {contact_msg}")
            else:
                logger.info(f"User {user_id} not reachable via normal method: {contact_msg}")
                
                # Second attempt: Try with all available accounts
                for account in all_accounts:
                    try:
                        alt_success, alt_msg = await self.account_manager.add_user_to_contacts(account, user_id)
                        if alt_success:
                            can_reach_user = True
                            logger.info(f"Successfully added user {user_id} to contacts via account {account.session_name}")
                            break
                    except Exception as alt_error:
                        logger.debug(f"Failed to add contact via {account.session_name}: {alt_error}")
                        continue
                
                # If still can't reach user, try to send a contact establishment message
                if not can_reach_user:
                    try:
                        send_success, send_msg = await self.account_manager.send_contact_message(primary_account, user_id)
                        if send_success:
                            await update.message.reply_text(f"📞 {send_msg}\n\nPlease reply to the message from {bot_account_info} and then try /invite again for better results.")
                            return  # Exit early - user should respond first
                        else:
                            logger.info(f"Could not send contact message: {send_msg}")
                    except Exception as send_error:
                        logger.warning(f"Error sending contact message: {send_error}")
                    
        except Exception as contact_error:
            logger.warning(f"Error checking contact status: {contact_error}")
        
        # Show progress based on contact establishment
        if can_reach_user:
            await update.message.reply_text(f"✅ Contact established! Processing invitations to {len(all_groups)} groups...")
        else:
            await update.message.reply_text(f"⚠️ Contact issues detected. Attempting to add to {len(all_groups)} groups anyway...")
        
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
            
            # Add user directly to group
            try:
                success, message = await self.account_manager.add_user_to_group(
                    account, user_id, group.group_id, group.invite_link
                )
                
                if success:
                    # Check the type of success
                    if "already in group" in message.lower():
                        already_member.append(group.group_name)
                        logger.info(f"User {user_id} already in group {group.group_name}")
                    else:
                        successful_invites.append(group.group_name)
                        logger.info(f"Successfully processed user {user_id} for group {group.group_name}")
                    
                    # Record successful invitation
                    self.cooldown_manager.record_invite_attempt(user_id, group.group_id, True)
                else:
                    # Failed to add - likely privacy settings issue
                    if "Cannot add:" in message:
                        failed_invites.append(f"{group.group_name}: {message}")
                    else:
                        failed_invites.append(f"{group.group_name}: {message}")
                    
                    # Record failed attempt
                    self.cooldown_manager.record_invite_attempt(user_id, group.group_id, False)
                    
            except Exception as e:
                failed_invites.append(f"{group.group_name}: Error - {str(e)}")
                logger.error(f"Error adding user {user_id} to group {group.group_name}: {e}")
            
            # Small delay between invitations to avoid rate limiting
            if i < len(all_groups) - 1:  # Don't delay after the last invitation
                await asyncio.sleep(2)  # Increased delay for direct adding
        
        # Update user's last invite time
        self.cooldown_manager.update_user_last_invite_time(user_id)
        
        # Prepare result message
        total_processed = len(successful_invites) + len(already_member)
        
        # Simple and direct results
        if successful_invites:
            result_message = f"✅ Successfully added to {len(successful_invites)} groups!\n"
            for group_name in successful_invites:
                result_message += f"• {group_name}\n"
        elif already_member:
            result_message = f"ℹ️ You are already a member of all {len(already_member)} groups.\n"
        elif failed_invites:
            result_message = f"❌ Could not add you to some groups.\n\n"
            
            # Check for specific PEER_ID_INVALID errors
            contact_errors = []
            privacy_errors = []
            other_errors = []
            invite_link_available = []
            user_not_accessible = []
            
            for failure in failed_invites:
                if "user must message our bot account first" in failure.lower() or \
                   "contact check failed" in failure.lower():
                    contact_errors.append(failure)
                elif "user not found or not accessible" in failure.lower() or \
                     "user not accessible" in failure.lower():
                    user_not_accessible.append(failure)
                elif "privacy" in failure.lower():
                    privacy_errors.append(failure)
                elif "invite link:" in failure.lower():
                    invite_link_available.append(failure)
                else:
                    other_errors.append(failure)
            
            # Provide specific instructions based on error types
            if user_not_accessible:
                result_message += f"<b>❌ User Not Accessible ({len(user_not_accessible)} groups):</b>\n"
                result_message += f"<i>The bot cannot reach you due to privacy settings:</i>\n"
                result_message += f"1. Please start a conversation with {bot_account_info}\n"
                result_message += f"2. Send any message (like 'hi') to establish contact\n"
                result_message += f"3. Then try /invite again\n\n"
                result_message += f"<i>This is required due to Telegram's privacy protection.</i>\n\n"
            
            if contact_errors:
                result_message += f"<b>🔗 Contact Issues ({len(contact_errors)} groups):</b>\n"
                result_message += f"<i>Additional contact establishment needed:</i>\n"
                result_message += f"1. Make sure you replied to {bot_account_info}\n"
                result_message += f"2. Check if conversation is started\n"
                result_message += f"3. Then try /invite again\n\n"
                
                for error in contact_errors[:3]:  # Show max 3 examples
                    result_message += f"• {error}\n"
                if len(contact_errors) > 3:
                    result_message += f"• ... and {len(contact_errors) - 3} more\n"
                result_message += "\n"
            
            if invite_link_available:
                result_message += f"<b>🔗 Manual Join Required ({len(invite_link_available)} groups):</b>\n"
                result_message += f"<i>Click these invite links to join manually:</i>\n"
                for error in invite_link_available:
                    result_message += f"• {error}\n"
                result_message += "\n"
            
            if privacy_errors:
                result_message += f"<b>🔒 Privacy Settings ({len(privacy_errors)} groups):</b>\n"
                result_message += f"<i>Check your Telegram privacy settings:</i>\n"
                result_message += f"1. Go to Settings → Privacy & Security\n"
                result_message += f"2. Check 'Groups & Channels' settings\n"
                result_message += f"3. Allow adding to groups\n\n"
                for error in privacy_errors:
                    result_message += f"• {error}\n"
                result_message += "\n"
            
            if other_errors:
                result_message += f"<b>⚠️ Other Issues ({len(other_errors)} groups):</b>\n"
                for error in other_errors:
                    result_message += f"• {error}\n"
                result_message += "\n"
            
            result_message += f"<b>💡 General Tips:</b>\n"
            result_message += f"• Make sure you haven't blocked our bot accounts\n"
            result_message += f"• Check that you're not already in these groups\n"
            result_message += f"• Contact admin if problems persist"
        else:
            result_message = "😔 No groups are available right now."
        
        await update.message.reply_text(result_message, parse_mode=ParseMode.HTML)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command"""
        # Update user info in database
        self._update_user_info(update.effective_user)
        
        user_id = update.effective_user.id
        
        # Check access level
        if self._is_admin(user_id):
            status_text = "👑 **You are an administrator**"
        elif self._is_whitelisted(user_id):
            status_text = "✅ **You are whitelisted**"
        else:
            status_text = "❌ **You are not whitelisted, contact administrator**"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        user_id = update.effective_user.id
        
        help_text = "🆘 **Help**\n\n"
        
        if self._is_admin(user_id):
            # Admin commands
            help_text += "**📋 User Commands:**\n"
            help_text += "• `/start` - Welcome message\n"
            help_text += "• `/invite` - Get invitations to all groups\n"
            help_text += "• `/status` - Check your status\n"
            help_text += "• `/help` - This help\n\n"
            
            help_text += "**👑 Administrator Commands:**\n\n"
            
            help_text += "*Group & Account Management:*\n"
            help_text += "• `/groups_info` - List groups with ID and members\n"
            help_text += "• `/accounts_info` - List accounts with statuses\n"
            help_text += "• `/add_group (name) (link)` - Add group (auto-detects ID)\n"
            help_text += "• `/remove_group (id)` - Remove group\n"
            help_text += "• `/join_groups` - Join all accounts to groups\n\n"
            
            help_text += "*User Management:*\n"
            help_text += "• `/whitelist @username (days)` - Add to whitelist\n"
            help_text += "• `/remove_whitelist @username` - Remove from whitelist\n"
            help_text += "• `/blacklist @username (reason)` - Add to blacklist\n"
            help_text += "• `/unblacklist @username` - Remove from blacklist\n"
            help_text += "• `/blacklist_info (@username)` - Show blacklist info\n"
            help_text += "• `/blacklist_info` - Show blacklist info of all users\n"
            
        elif self._is_whitelisted(user_id):
            # Whitelisted user commands
            help_text += "**📋 Available Commands:**\n"
            help_text += "• `/start` - Welcome message\n"
            help_text += "• `/invite` - Get invitations to all groups\n"
            help_text += "• `/status` - Check your status\n"
            help_text += "• `/help` - This help\n\n"
            
            help_text += "**ℹ️ How to get an invitation:**\n"
            help_text += "1. Use the `/invite` command\n"
            help_text += "2. Wait for request processing\n"
            help_text += "3. Check your private messages\n\n"
            
            help_text += "**⚠️ Limitations:**\n"
            help_text += "• Available only to whitelisted users\n"
            help_text += "• There is a cooldown between invitations\n"
            
        else:
            # Non-whitelisted user
            help_text += "**❌ Access Restricted**\n\n"
            help_text += "You are not in the whitelist.\n"
            help_text += "To get access to the bot, contact the administrator.\n\n"
            help_text += "**📋 Available Commands:**\n"
            help_text += "• `/start` - Welcome message\n"
            help_text += "• `/status` - Check your status\n"
            help_text += "• `/help` - This help\n"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def block_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /block command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /block @username [hours]")
            return
        
        try:
            username_arg = context.args[0]
            hours = int(context.args[1]) if len(context.args) > 1 else 24
            
            # Remove @ if present
            username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
            
            # For now, we'll use a placeholder user_id (0) since we're working with usernames
            # In a real implementation, you'd want to resolve the username to a user_id
            user_id = 0  # Placeholder - you may need to implement username resolution
            
            self.cooldown_manager.block_user(user_id, hours)
            await update.message.reply_text(f"✅ User @{username} blocked for {hours} hours.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Hours must be a number.")
    
    async def unblock_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /unblock command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unblock @username")
            return
        
        username_arg = context.args[0]
        
        # Remove @ if present
        username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
        
        # For now, we'll use a placeholder user_id (0) since we're working with usernames
        # In a real implementation, you'd want to resolve the username to a user_id
        user_id = 0  # Placeholder - you may need to implement username resolution
        
        self.cooldown_manager.unblock_user(user_id)
        await update.message.reply_text(f"✅ User @{username} unblocked.")
    
    async def join_groups_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /join_groups command - automatically join all accounts to all groups"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Send initial message
        status_message = await update.message.reply_text("🔄 Starting automatic group joining process...")
        
        try:
            # Get all active groups
            active_groups = self.group_manager.get_active_groups()
            
            if not active_groups:
                await status_message.edit_text("❌ No active groups found.")
                return
            
            # Start auto-join process
            results = await self.account_manager.auto_join_all_groups(active_groups)
            
            # Format results message in the new style
            response_lines = ["🔄 Auto-join (Updated)\n"]
            
            total_success_groups = 0
            total_failed_groups = 0
            
            # Process each group
            for group_name, group_results in results.items():
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
            response_lines.append("� Update Summary:")
            response_lines.append(f"• ✅ Successfully: {total_success_groups} groups")
            response_lines.append(f"• ❌ Failed: {total_failed_groups} groups")
            response_lines.append(f"• 📊 Total: {len(active_groups)} groups")
            
            response_text = "\n".join(response_lines)
            
            # Update the message
            await status_message.edit_text(response_text)
            
        except Exception as e:
            error_text = f"❌ Error during auto-join process: {str(e)}"
            try:
                await status_message.edit_text(error_text)
            except:
                await update.message.reply_text(error_text)
    
    async def whitelist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /whitelist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /whitelist @username <days>\n"
                "Example: /whitelist @john_doe 30"
            )
            return
        
        try:
            username_arg = context.args[0]
            days = int(context.args[1])
            
            # Remove @ if present
            username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
            
            if days <= 0:
                await update.message.reply_text("❌ Days must be a positive number.")
                return
            
            # Try to get user_id from database first (if user has interacted with bot before)
            user_id = self.database_manager.get_user_id_by_username(username)
            
            if user_id is None:
                await update.message.reply_text(
                    f"⚠️ Cannot find user ID for @{username}. "
                    f"The user needs to start the bot first by sending /start command. "
                    f"After that, you can add them to whitelist."
                )
                return
            
            success = self.whitelist_manager.add_to_whitelist(
                user_id, days, update.effective_user.id, f"@{username}"
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ User @{username} (ID: {user_id}) added to whitelist for {days} days."
                )
            else:
                await update.message.reply_text("❌ Failed to add user to whitelist.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Days must be a number.")
    
    async def remove_whitelist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /remove_whitelist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /remove_whitelist @username")
            return
        
        username_arg = context.args[0]
        
        # Remove @ if present
        username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
        
        # Try to get user_id from database
        user_id = self.database_manager.get_user_id_by_username(username)
        
        if user_id is None:
            await update.message.reply_text(
                f"⚠️ Cannot find user ID for @{username}. "
                f"User may not have interacted with the bot or was never whitelisted."
            )
            return
        
        success = self.whitelist_manager.remove_from_whitelist(user_id)
        
        if success:
            await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) removed from whitelist.")
        else:
            await update.message.reply_text(f"❌ User @{username} (ID: {user_id}) not found in whitelist.")
    
    async def add_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /add_group command - now with auto ID detection"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /add_group <group_name> <invite_link>\n"
                "Example: /add_group \"Test Group\" https://t.me/+abc123\n\n"
                "💡 The bot will automatically join the group and detect its ID!"
            )
            return
        
        try:
            group_name = context.args[0]
            invite_link = context.args[1]
            
            if not invite_link.startswith('https://t.me/'):
                await update.message.reply_text("❌ Invalid invite link. Must start with https://t.me/")
                return
            
            # Send initial message
            status_message = await update.message.reply_text(f"� Joining group '{group_name}' to detect ID...")
            
            # Use new method with auto ID detection
            result = await self.group_manager.add_group_with_auto_id(
                group_name, invite_link, self.account_manager
            )
            
            if result["success"]:
                # Prepare detailed response
                group_id = result.get("group_id")
                join_results = result.get("join_results", {})
                member_count = result.get("member_count")
                join_message = result.get("join_message", "")
                
                response_text = f"✅ Group '{group_name}' added successfully!\n"
                response_text += f"🆔 Auto-detected ID: {group_id}\n"
                response_text += f"🔗 Link: {invite_link}\n\n"
                
                # Add join message
                if join_message:
                    response_text += f"📝 Join Status: {join_message}\n\n"
                
                # Add join results
                if join_results:
                    successful_joins = join_results.get("success", [])
                    failed_joins = join_results.get("failed", [])
                    
                    response_text += f"📊 Account Join Results:\n"
                    response_text += f"• ✅ Successfully joined: {len(successful_joins)} accounts\n"
                    if successful_joins:
                        response_text += f"  - {', '.join(successful_joins)}\n"
                    
                    if failed_joins:
                        response_text += f"• ❌ Failed to join: {len(failed_joins)} accounts\n"
                        response_text += f"  - {', '.join(failed_joins)}\n"
                    
                    response_text += "\n"
                
                # Add member count if available
                if member_count is not None:
                    response_text += f"👥 Current member count: {member_count}"
                else:
                    response_text += "❓ Could not retrieve member count"
                
                await status_message.edit_text(response_text)
            else:
                await status_message.edit_text(f"❌ Failed to add group: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error in add_group_command: {e}")
            await update.message.reply_text(f"❌ An error occurred while adding the group: {str(e)}")
    
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
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Send initial message
        status_message = await update.message.reply_text("📊 Collecting group information and updating member counts...")
        
        # Update member counts for all groups
        update_results = await self.group_manager.update_all_groups_member_count(self.account_manager)
        
        # Get updated group statistics
        group_stats = self.group_manager.get_group_stats()
        
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
        
        await status_message.edit_text(text)
    
    async def accounts_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /accounts_info command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Get account statistics with detailed info
        account_stats = await self.account_manager.get_detailed_account_stats()
        
        # Build response according to the new format
        response_lines = ["🔄 Accounts Information (Updated)\n"]
        
        successful_accounts = 0
        failed_accounts = 0
        
        if account_stats['accounts_details']:
            for account in account_stats['accounts_details']:
                account_name = account['session_name']
                account_id = account.get('user_id', 'Unknown')
                
                if account.get('is_active', False) and account.get('is_connected', False):
                    status_icon = "✅"
                    successful_accounts += 1
                else:
                    status_icon = "❌"
                    failed_accounts += 1
                
                response_lines.append(f"{status_icon} {account_name} (ID: {account_id})")
        else:
            response_lines.append("❌ No accounts found")
            failed_accounts = 1
        
        # Add summary
        total_accounts = successful_accounts + failed_accounts
        response_lines.append("")
        response_lines.append("📈 Update Summary:")
        response_lines.append(f"• ✅ Successfully: {successful_accounts} accounts")
        response_lines.append(f"• ❌ Failed: {failed_accounts} accounts")
        response_lines.append(f"• 📊 Total: {total_accounts}")
        
        response_text = "\n".join(response_lines)
        await update.message.reply_text(response_text)
    
    async def blacklist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /blacklist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /blacklist @username <reason>\n"
                "Example: /blacklist @john_doe Spam behavior"
            )
            return
        
        try:
            username_arg = context.args[0]
            reason = " ".join(context.args[1:])
            
            # Remove @ if present
            username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
            
            # Try to get user_id from database
            user_id = self.database_manager.get_user_id_by_username(username)
            
            if user_id is None:
                await update.message.reply_text(
                    f"⚠️ Cannot find user ID for @{username}. "
                    f"The user needs to interact with the bot first by sending /start command. "
                    f"After that, you can add them to blacklist."
                )
                return
            
            success = self.blacklist_manager.add_user(
                user_id, reason, update.effective_user.id, f"@{username}"
            )
            
            if success:
                await update.message.reply_text(
                    f"🚫 User @{username} (ID: {user_id}) added to blacklist.\n"
                    f"**Reason:** {reason}"
                )
            else:
                await update.message.reply_text("❌ Failed to add user to blacklist.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error processing command: {str(e)}")
    
    async def unblacklist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /unblacklist command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unblacklist @username")
            return
        
        try:
            username_arg = context.args[0]
            
            # Remove @ if present
            username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
            
            # Try to get user_id from database
            user_id = self.database_manager.get_user_id_by_username(username)
            
            if user_id is None:
                await update.message.reply_text(
                    f"⚠️ Cannot find user ID for @{username}. "
                    f"User may not have interacted with the bot or was never blacklisted."
                )
                return
            
            success = self.blacklist_manager.remove_user(user_id)
            
            if success:
                await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) removed from blacklist.")
            else:
                await update.message.reply_text(f"❌ User @{username} (ID: {user_id}) not found in blacklist.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error processing command: {str(e)}")
    
    async def blacklist_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /blacklist_info command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # If username provided, show specific user info
        if context.args:
            try:
                username_arg = context.args[0]
                
                # Remove @ if present
                username = username_arg.replace('@', '') if username_arg.startswith('@') else username_arg
                
                # Try to get user_id from database
                user_id = self.database_manager.get_user_id_by_username(username)
                
                if user_id is None:
                    await update.message.reply_text(
                        f"⚠️ Cannot find user ID for @{username}. "
                        f"User may not have interacted with the bot."
                    )
                    return
                
                entry = self.blacklist_manager.get_user_info(user_id)
                
                if entry:
                    from datetime import datetime
                    added_date = datetime.fromtimestamp(entry.added_date)
                    
                    info_text = f"🔄 **Blacklist Information (Updated)**\n\n"
                    info_text += f"🚫 @{username} (ID: {user_id})\n\n"
                    info_text += f"📈 **Update Summary:**\n"
                    info_text += f"• 📊 Total: 1\n"
                    info_text += f"• 📝 Reason: {entry.reason}\n"
                    info_text += f"• 👤 Added by: {entry.added_by}\n"
                    info_text += f"• 📅 Added: {added_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    info_text += f"• ⚡ Status: {'Active' if entry.is_active else 'Inactive'}"
                    
                    await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(f"❌ User @{username} (ID: {user_id}) not found in blacklist.")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ Error processing command: {str(e)}")
        else:
            # Show blacklist summary
            summary = self.blacklist_manager.get_blacklist_summary()
            await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)
    
    def start_bot(self):
        """Synchronous bot startup"""
        
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
        
        try:
            if self.account_manager:
                await self.account_manager.shutdown()
            
            # Note: Automatic group statistics collection disabled
            # if self.group_stats_collector:
            #     await self.group_stats_collector.stop_collection()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        

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
        pass
    except Exception as e:
        logger.error(f"Critical error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())