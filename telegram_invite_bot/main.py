"""
Main invite bot
"""
import asyncio
import logging
import os
import sys
from typing import Dict, List

# Добавляем путь к модулям
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

# Настройка уровней логирования для важных компонентов
logging.getLogger('src.account_manager').setLevel(logging.INFO)
logging.getLogger('src.group_manager').setLevel(logging.INFO)
logging.getLogger('src.cooldown_manager').setLevel(logging.ERROR)
logging.getLogger('src.database_manager').setLevel(logging.ERROR)
logging.getLogger('src.group_stats_collector').setLevel(logging.ERROR)
logging.getLogger('__main__').setLevel(logging.ERROR)

# Отключение логов от внешних библиотек
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
        data_dir = os.path.join(script_dir, '..', 'data')
        
        self.config_manager = ConfigManager(config_dir)
        self.account_manager = AccountManager(self.config_manager)
        self.group_manager = GroupManager(self.config_manager)
        self.cooldown_manager = CooldownManager(config=self.config_manager.bot_config)
        
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
        
        # Initialize managers
        await self.account_manager.initialize()
        self.group_manager.initialize()
        
        # Create bot application
        self.application = Application.builder().token(self.bot_config.bot_token).build()
        
        # Register handlers
        self._register_handlers()
        
        # Start group statistics collection
        await self.group_stats_collector.start_collection()
        
    
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
        self.application.add_handler(CommandHandler("block", self.block_user_command))
        self.application.add_handler(CommandHandler("unblock", self.unblock_user_command))
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator"""
        return self.whitelist_manager.is_admin(user_id)
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        return self.whitelist_manager.is_user_whitelisted(user_id)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        user = update.effective_user
        
        welcome_text = f"""
🤖 **Welcome to the Invite Bot!**

Hello, {user.first_name}! 

This bot will help you get invitations to our groups.

**📋 Basic commands:**
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
        
        # Check access level
        if self._is_admin(user_id):
            status_text = "👑 **You are an administrator**"
        elif self._is_whitelisted(user_id):
            status_text = "✅ **You are whitelisted**"
        else:
            status_text = "❌ **You are not whitelisted, please contact the administrator**"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        user_id = update.effective_user.id
        
        help_text = "🆘 **Help**\n\n"
        
        if self._is_admin(user_id):
            # Admin commands
            help_text += "**📋 User commands:**\n"
            help_text += "• `/start` - Welcome message\n"
            help_text += "• `/invite` - Get invitations to all groups\n"
            help_text += "• `/status` - Check your status\n"
            help_text += "• `/help` - This help\n\n"
            
            help_text += "**👑 Administrator commands:**\n\n"
            
            help_text += "*Group and account management:*\n"
            help_text += "• `/groups_info` - List groups with IDs and members\n"
            help_text += "• `/accounts_info` - List accounts with statuses\n"
            help_text += "• `/add_group (id) (name) (link)` - Add group\n"
            help_text += "• `/remove_group (id)` - Remove group\n"
            help_text += "• `/join_groups` - Join all accounts to groups\n\n"
            
            help_text += "*User management:*\n"
            help_text += "• `/whitelist @username (days)` - Add to whitelist\n"
            help_text += "• `/remove_whitelist @username` - Remove from whitelist\n"
            help_text += "• `/block @username [hours]` - Block user\n"
            help_text += "• `/unblock @username` - Unblock user\n"
            
        elif self._is_whitelisted(user_id):
            # Whitelisted user commands
            help_text += "**📋 Доступные команды:**\n"
            help_text += "• `/start` - Приветственное сообщение\n"
            help_text += "• `/invite` - Получить приглашения во все группы\n"
            help_text += "• `/status` - Проверить свой статус\n"
            help_text += "• `/help` - Эта справка\n\n"
            
            help_text += "**ℹ️ Как получить приглашение:**\n"
            help_text += "1. Используйте команду `/invite`\n"
            help_text += "2. Дождитесь обработки запроса\n"
            help_text += "3. Проверьте личные сообщения\n\n"
            
            help_text += "**⚠️ Ограничения:**\n"
            help_text += "• Доступно только пользователям в whitelist\n"
            help_text += "• Между приглашениями есть кулдаун\n"
            
        else:
            # Non-whitelisted user
            help_text += "**❌ Доступ ограничен**\n\n"
            help_text += "Вы не находитесь в whitelist.\n"
            help_text += "Для получения доступа к боту обратитесь к администратору.\n\n"
            help_text += "**📋 Доступные команды:**\n"
            help_text += "• `/start` - Приветственное сообщение\n"
            help_text += "• `/status` - Проверить свой статус\n"
            help_text += "• `/help` - Эта справка\n"
        
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
        
        await update.message.reply_text("🔄 Starting automatic group joining process...")
        
        try:
            # Get all active groups
            active_groups = self.group_manager.get_active_groups()
            
            if not active_groups:
                await update.message.reply_text("❌ No active groups found.")
                return
            
            # Start auto-join process
            results = await self.account_manager.auto_join_all_groups(active_groups)
            
            # Format results message
            response_lines = ["✅ Auto-join process completed!\n"]
            
            total_success = 0
            total_failed = 0
            
            for group_name, group_results in results.items():
                success_count = len(group_results["success"])
                failed_count = len(group_results["failed"])
                
                total_success += success_count
                total_failed += failed_count
                
                response_lines.append(f"📋 {group_name}")
                response_lines.append(f"  ✅ Joined: {success_count}")
                response_lines.append(f"  ❌ Failed: {failed_count}")
                
                if group_results["failed"]:
                    response_lines.append(f"  Failed accounts: {', '.join(group_results['failed'][:3])}")
                    if len(group_results["failed"]) > 3:
                        response_lines.append(f"  ...and {len(group_results['failed']) - 3} more")
                
                response_lines.append("")
            
            response_lines.append(f"📊 Total Summary:")
            response_lines.append(f"✅ Total Successful: {total_success}")
            response_lines.append(f"❌ Total Failed: {total_failed}")
            
            response_text = "\n".join(response_lines)
            
            # Split message if too long
            if len(response_text) > 4000:
                response_text = response_text[:4000] + "...\n\n📊 Check logs for full details."
            
            await update.message.reply_text(response_text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error during auto-join process: {str(e)}")
    
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
            
            # For now, we'll use a placeholder user_id (0) since we're working with usernames
            # In a real implementation, you'd want to resolve the username to a user_id
            user_id = 0  # Placeholder - you may need to implement username resolution
            
            success = self.whitelist_manager.add_to_whitelist(
                user_id, days, update.effective_user.id, f"@{username}"
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ User @{username} added to whitelist for {days} days."
                )
                
                # Record in database
                self.database_manager.record_invitation(
                    user_id, 0, "Whitelist Addition", True, f"Added by admin for {days} days"
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
        
        # For now, we'll use a placeholder user_id (0) since we're working with usernames
        # In a real implementation, you'd want to resolve the username to a user_id
        user_id = 0  # Placeholder - you may need to implement username resolution
        
        success = self.whitelist_manager.remove_from_whitelist(user_id)
        
        if success:
            await update.message.reply_text(f"✅ User @{username} removed from whitelist.")
        else:
            await update.message.reply_text(f"❌ User @{username} not found in whitelist.")
    
    async def add_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /add_group command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /add_group <group_id> <group_name> <invite_link>\n"
                "Example: /add_group -1001234567890 \"Test Group\" https://t.me/+abc123"
            )
            return
        
        try:
            group_id = int(context.args[0])
            group_name = context.args[1]
            invite_link = context.args[2]
            
            if not invite_link.startswith('https://t.me/'):
                await update.message.reply_text("❌ Invalid invite link. Must start with https://t.me/")
                return
            
            success = self.group_manager.add_group(group_id, group_name, invite_link)
            
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
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Get group statistics
        group_stats = self.group_manager.get_group_stats()
        db_stats = self.database_manager.get_overall_statistics()
        
        text = "🏢 **Groups Information**\n\n"
        
        for group in group_stats['groups_details']:
            # Get group info from database for member count
            group_id = group['group_id']
            member_count = "Unknown"
            
            # Try to get member count from database stats
            if db_stats and 'groups' in db_stats:
                for db_group in db_stats.get('groups', []):
                    if db_group.get('group_id') == group_id:
                        member_count = db_group.get('member_count', 'Unknown')
                        break
            
            status = "✅" if group['is_active'] else "❌"
            text += f"{status} **{group['group_name']}** (ID: `{group_id}`)\n"
            text += f"   👥 Members: {member_count}\n\n"
        
        if not group_stats['groups_details']:
            text += "No groups found."
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def accounts_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /accounts_info command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        # Get account statistics
        account_stats = self.account_manager.get_account_stats()
        
        text = "� **Accounts Information**\n\n"
        
        if account_stats['accounts_details']:
            for account in account_stats['accounts_details']:
                status = "✅" if account.get('is_active', False) else "❌"
                text += f"{status} **{account['session_name']}**\n"
                
                # Show phone if available
                if 'phone' in account:
                    text += f"   📱 Phone: {account['phone']}\n"
                
                # Show connection status
                if account.get('is_connected', False):
                    username = account.get('username', 'Unknown')
                    first_name = account.get('first_name', 'Unknown')
                    text += f"   🔗 Connected: {first_name} (@{username})\n"
                else:
                    text += f"   ❌ Not connected\n"
                
                text += "\n"
        else:
            text += "No accounts found."
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
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
            
            # Stop group statistics collection
            if self.group_stats_collector:
                await self.group_stats_collector.stop_collection()
                
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