"""
Основной бот-приглашающий
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

# Настройка логирования
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
    """Основной класс бота-приглашающего"""
    
    def __init__(self):
        # Получаем директорию скрипта для правильных путей
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, 'config')
        
        self.config_manager = ConfigManager(config_dir)
        self.account_manager = AccountManager(self.config_manager)
        self.group_manager = GroupManager(self.config_manager)
        self.cooldown_manager = CooldownManager()
        
        self.bot_config = self.config_manager.bot_config
        self.application = None
        
    async def initialize(self):
        """Инициализация бота"""
        logger.info("Инициализация бота...")
        
        # Инициализируем менеджеры
        await self.account_manager.initialize()
        self.group_manager.initialize()
        
        # Создаем приложение бота
        self.application = Application.builder().token(self.bot_config.bot_token).build()
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("Бот инициализирован успешно")
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Админские команды
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("block", self.block_user_command))
        self.application.add_handler(CommandHandler("unblock", self.unblock_user_command))
        self.application.add_handler(CommandHandler("reset", self.reset_stats_command))
        
        # Обработчик callback-кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        return user_id in self.bot_config.admin_user_ids
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """Проверка, находится ли пользователь в белом списке"""
        return user_id in self.bot_config.whitelist_user_ids or self._is_admin(user_id)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")
        
        welcome_text = f"""
🤖 **Добро пожаловать в бота-приглашающего!**

Привет, {user.first_name}! 

Этот бот поможет вам получить приглашения в наши группы.

**Доступные команды:**
• /invite - Получить приглашение в группу
• /status - Проверить свой статус
• /help - Помощь

Для получения приглашения используйте команду /invite
        """
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /invite"""
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"Запрос приглашения от пользователя {user_id} ({user.username})")
        
        # Проверяем, есть ли пользователь в белом списке
        if not self._is_whitelisted(user_id):
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту. Обратитесь к администратору."
            )
            return
        
        # Проверяем кулдаун пользователя
        can_invite, cooldown_message = self.cooldown_manager.can_user_request_invite(user_id)
        if not can_invite:
            await update.message.reply_text(f"⏰ {cooldown_message}")
            return
        
        # Получаем доступные группы
        available_groups = self.group_manager.get_available_groups_for_user(user_id)
        if not available_groups:
            await update.message.reply_text(
                "😔 К сожалению, сейчас нет доступных групп для приглашения. Попробуйте позже."
            )
            return
        
        # Выбираем лучшую группу
        target_group = self.group_manager.select_best_group_for_user(user_id)
        if not target_group:
            await update.message.reply_text(
                "😔 Не удалось найти подходящую группу. Попробуйте позже."
            )
            return
        
        # Проверяем кулдаун группы
        can_invite_group, group_message = self.cooldown_manager.can_invite_to_group(target_group.group_id)
        if not can_invite_group:
            await update.message.reply_text(f"⏰ {group_message}")
            return
        
        # Получаем доступный аккаунт
        account = self.account_manager.get_available_account(target_group.group_id)
        if not account:
            await update.message.reply_text(
                "😔 Сейчас нет доступных аккаунтов для отправки приглашения. Попробуйте позже."
            )
            return
        
        # Отправляем приглашение
        await update.message.reply_text("🔄 Отправляю приглашение...")
        
        success = await self.account_manager.send_invite(
            account, user_id, target_group.invite_link
        )
        
        if success:
            # Записываем успешное приглашение
            self.cooldown_manager.record_invite_attempt(user_id, target_group.group_id, True)
            self.group_manager.record_invitation(user_id, target_group.group_id)
            
            await update.message.reply_text(
                f"✅ **Приглашение отправлено!**\\n\\n"
                f"Группа: {target_group.group_name}\\n"
                f"Ссылка: {target_group.invite_link}\\n\\n"
                f"Проверьте личные сообщения для получения приглашения.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Приглашение успешно отправлено пользователю {user_id}")
        else:
            # Записываем неудачную попытку
            self.cooldown_manager.record_invite_attempt(user_id, target_group.group_id, False)
            
            await update.message.reply_text(
                "❌ Не удалось отправить приглашение. Попробуйте позже."
            )
            
            logger.error(f"Не удалось отправить приглашение пользователю {user_id}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user_id = update.effective_user.id
        
        if not self._is_whitelisted(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        # Получаем статистику пользователя
        user_stats = self.cooldown_manager.get_user_stats(user_id)
        
        status_text = f"""
📊 **Ваш статус**

🎫 Приглашений сегодня: {user_stats['invite_count_today']}/{self.cooldown_manager.max_invites_per_day}
🎯 Осталось приглашений: {user_stats['remaining_invites']}

{"🚫 Заблокирован" if user_stats['is_blocked'] else "✅ Активен"}

{"⏰ Можно запросить приглашение" if user_stats['can_invite'] else "⏳ Ожидание кулдауна"}
        """
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        # Получаем статистику
        cooldown_stats = self.cooldown_manager.get_global_stats()
        account_stats = self.account_manager.get_account_stats()
        group_stats = self.group_manager.get_group_stats()
        
        stats_text = f"""
📈 **Статистика бота**

**Пользователи:**
👥 Всего пользователей: {cooldown_stats['total_users']}
🚫 Заблокированных: {cooldown_stats['active_blocks']}
🎫 Приглашений сегодня: {cooldown_stats['total_invites_today']}

**Аккаунты:**
👤 Всего аккаунтов: {account_stats['total_accounts']}
✅ Активных: {account_stats['active_accounts']}
📤 Приглашений от аккаунтов: {account_stats['total_daily_invites']}

**Группы:**
🏢 Всего групп: {group_stats['total_groups']}
✅ Активных: {group_stats['active_groups']}
📥 Приглашений в группы: {group_stats['total_daily_invites']}
        """
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🆘 **Помощь**

**Основные команды:**
• /start - Приветствие
• /invite - Получить приглашение в группу
• /status - Проверить свой статус
• /help - Эта справка

**Как получить приглашение:**
1. Используйте команду /invite
2. Дождитесь обработки запроса
3. Проверьте личные сообщения

**Ограничения:**
• Максимум 10 приглашений в день
• Перерыв 5 минут между приглашениями
• Доступно только пользователям из белого списка

По вопросам обращайтесь к администратору.
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /admin"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("👥 Аккаунты", callback_data="admin_accounts")
            ],
            [
                InlineKeyboardButton("🏢 Группы", callback_data="admin_groups"),
                InlineKeyboardButton("⏰ Кулдауны", callback_data="admin_cooldowns")
            ],
            [
                InlineKeyboardButton("🔄 Сбросить статистику", callback_data="admin_reset"),
                InlineKeyboardButton("🧹 Очистка", callback_data="admin_cleanup")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 **Панель администратора**\\n\\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def block_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /block"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        if not context.args:
            await update.message.reply_text("Использование: /block <user_id> [hours]")
            return
        
        try:
            user_id = int(context.args[0])
            hours = int(context.args[1]) if len(context.args) > 1 else 24
            
            self.cooldown_manager.block_user(user_id, hours)
            await update.message.reply_text(f"✅ Пользователь {user_id} заблокирован на {hours} часов.")
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используйте числа.")
    
    async def unblock_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /unblock"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        if not context.args:
            await update.message.reply_text("Использование: /unblock <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            self.cooldown_manager.unblock_user(user_id)
            await update.message.reply_text(f"✅ Пользователь {user_id} разблокирован.")
            
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя.")
    
    async def reset_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /reset"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        self.cooldown_manager.reset_daily_stats()
        self.account_manager.reset_daily_stats()
        self.group_manager.reset_daily_stats()
        
        await update.message.reply_text("✅ Дневная статистика сброшена.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if not self._is_admin(query.from_user.id):
            await query.edit_message_text("❌ Доступ запрещен.")
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
        """Показать детальную статистику"""
        recent_activity = self.cooldown_manager.get_recent_activity(24)
        
        stats_text = "📊 **Детальная статистика (24 часа)**\\n\\n"
        
        if recent_activity:
            stats_text += "**Активные пользователи:**\\n"
            for activity in recent_activity[:10]:  # Показываем только первые 10
                last_time = datetime.fromtimestamp(activity['last_invite_time'])
                stats_text += f"• {activity['user_id']}: {activity['invite_count_today']} приглашений, последнее: {last_time.strftime('%H:%M')}\\n"
        else:
            stats_text += "Активности не было."
        
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_account_details(self, query):
        """Показать детали аккаунтов"""
        account_stats = self.account_manager.get_account_stats()
        
        details_text = "👤 **Состояние аккаунтов**\\n\\n"
        
        for account in account_stats['accounts_details']:
            status = "✅" if account['is_active'] else "❌"
            details_text += f"{status} {account['session_name']}: {account['daily_invites']} приглашений\\n"
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_group_details(self, query):
        """Показать детали групп"""
        group_stats = self.group_manager.get_group_stats()
        
        details_text = "🏢 **Состояние групп**\\n\\n"
        
        for group in group_stats['groups_details']:
            status = "✅" if group['is_active'] else "❌"
            details_text += f"{status} {group['group_name']}: {group['daily_invites']}/{group['max_daily_invites']}\\n"
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_cooldown_details(self, query):
        """Показать детали кулдаунов"""
        global_stats = self.cooldown_manager.get_global_stats()
        
        details_text = f"""
⏰ **Настройки кулдаунов**

🕐 Кулдаун приглашений: {global_stats['invite_cooldown_seconds']}с
🕑 Кулдаун групп: {global_stats['group_cooldown_seconds']}с
🎫 Макс. приглашений в день: {global_stats['max_invites_per_day']}

👥 Всего пользователей: {global_stats['total_users']}
🚫 Заблокированных: {global_stats['active_blocks']}
        """
        
        await query.edit_message_text(details_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _confirm_reset(self, query):
        """Подтверждение сброса статистики"""
        self.cooldown_manager.reset_daily_stats()
        self.account_manager.reset_daily_stats()
        self.group_manager.reset_daily_stats()
        
        await query.edit_message_text("✅ Вся дневная статистика была сброшена.")
    
    async def _perform_cleanup(self, query):
        """Выполнение очистки"""
        self.cooldown_manager.cleanup_expired_blocks()
        await query.edit_message_text("✅ Очистка завершена. Истекшие блокировки удалены.")
    
    def start_bot(self):
        """Синхронный запуск бота"""
        logger.info("Запуск бота...")
        
        try:
            # Инициализируем в отдельном event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.initialize())
                
                # Запускаем polling
                self.application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
    
    async def run(self):
        """Запуск бота"""
        logger.info("Запуск бота...")
        
        try:
            await self.initialize()
            # Используем run_polling который правильно управляет event loop
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
    
    async def shutdown(self):
        """Завершение работы бота"""
        logger.info("Завершение работы бота...")
        
        try:
            if self.account_manager:
                await self.account_manager.shutdown()
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")
        
        logger.info("Бот остановлен")

def main():
    """Главная функция"""
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    # Получаем директорию скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Создаем необходимые директории
    os.makedirs(os.path.join(script_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(script_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(script_dir, "data", "sessions"), exist_ok=True)
    
    # Запускаем бота
    bot = InviteBot()
    
    try:
        # Используем run_polling которая сама управляет event loop
        bot.start_bot()
    except KeyboardInterrupt:
        logger.info("Остановка по сигналу пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())