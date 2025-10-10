"""
Менеджер пользовательских аккаунтов Telegram
"""
import asyncio
import logging
import time
import random
from typing import List, Optional, Dict
from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered, UserDeactivated, SessionPasswordNeeded
from pyrogram.types import User

from config.config import UserAccount, ConfigManager

logger = logging.getLogger(__name__)

class AccountManager:
    """Менеджер пользовательских аккаунтов для приглашений"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.clients: Dict[str, Client] = {}
        self.accounts: List[UserAccount] = []
        
        # Получаем абсолютный путь к директории сессий
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.session_dir = os.path.join(script_dir, "data", "sessions")
        
    async def initialize(self):
        """Инициализация менеджера аккаунтов"""
        self.accounts = self.config_manager.load_accounts()
        logger.info(f"Загружено {len(self.accounts)} аккаунтов")
        
        # Создаем клиентов для каждого аккаунта
        for account in self.accounts:
            if account.is_active:
                await self._create_client(account)
    
    async def _create_client(self, account: UserAccount) -> Optional[Client]:
        """Создание клиента Pyrogram для аккаунта"""
        try:
            client = Client(
                name=account.session_name,
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone,
                workdir=self.session_dir
            )
            
            # Подключаемся к аккаунту
            await client.start()
            
            # Проверяем, что аккаунт активен
            me = await client.get_me()
            logger.info(f"Аккаунт {account.session_name} подключен: {me.first_name} (@{me.username})")
            
            self.clients[account.session_name] = client
            return client
            
        except AuthKeyUnregistered:
            logger.error(f"Аккаунт {account.session_name}: Неверный ключ авторизации")
            account.is_active = False
        except UserDeactivated:
            logger.error(f"Аккаунт {account.session_name}: Аккаунт деактивирован")
            account.is_active = False
        except SessionPasswordNeeded:
            logger.error(f"Аккаунт {account.session_name}: Требуется 2FA пароль")
            account.is_active = False
        except Exception as e:
            logger.error(f"Ошибка подключения аккаунта {account.session_name}: {e}")
            account.is_active = False
        
        return None
    
    def get_available_account(self, group_id: int = None) -> Optional[UserAccount]:
        """Получение доступного аккаунта для приглашения"""
        available_accounts = []
        
        for account in self.accounts:
            if not account.is_active:
                continue
                
            # Проверяем, не превышен ли дневной лимит
            if account.daily_invites_count >= 50:  # Лимит приглашений в день
                continue
                
            # Проверяем кулдаун аккаунта
            if time.time() - account.last_used < 60:  # 1 минута между использованиями
                continue
                
            # Если указана группа, проверяем, назначен ли аккаунт на эту группу
            if group_id and account.groups_assigned:
                if group_id not in account.groups_assigned:
                    continue
            
            available_accounts.append(account)
        
        if not available_accounts:
            return None
        
        # Выбираем аккаунт с наименьшим количеством приглашений за день
        return min(available_accounts, key=lambda x: x.daily_invites_count)
    
    async def send_invite(self, account: UserAccount, user_id: int, group_link: str) -> bool:
        """Отправка приглашения пользователю"""
        client = self.clients.get(account.session_name)
        if not client:
            logger.error(f"Клиент для аккаунта {account.session_name} не найден")
            return False
        
        try:
            # Отправляем приглашение
            message_text = f"🎉 Привет! Приглашаю тебя присоединиться к нашей группе: {group_link}"
            
            await client.send_message(user_id, message_text)
            
            # Обновляем статистику аккаунта
            account.last_used = time.time()
            account.daily_invites_count += 1
            
            # Сохраняем изменения
            self.config_manager.save_accounts(self.accounts)
            
            logger.info(f"Приглашение отправлено пользователю {user_id} через аккаунт {account.session_name}")
            return True
            
        except FloodWait as e:
            logger.warning(f"FloodWait для аккаунта {account.session_name}: ждем {e.value} секунд")
            # Деактивируем аккаунт временно
            account.is_active = False
            # Можно добавить логику для реактивации через определенное время
            await asyncio.sleep(e.value)
            account.is_active = True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка отправки приглашения через {account.session_name}: {e}")
            return False
    
    async def check_user_in_group(self, account: UserAccount, user_id: int, group_id: int) -> bool:
        """Проверка, состоит ли пользователь в группе"""
        client = self.clients.get(account.session_name)
        if not client:
            return False
        
        try:
            member = await client.get_chat_member(group_id, user_id)
            return member.status in ["member", "administrator", "creator"]
        except Exception as e:
            logger.debug(f"Пользователь {user_id} не найден в группе {group_id}: {e}")
            return False
    
    async def get_group_invite_link(self, account: UserAccount, group_id: int) -> Optional[str]:
        """Получение ссылки-приглашения для группы"""
        client = self.clients.get(account.session_name)
        if not client:
            return None
        
        try:
            chat = await client.get_chat(group_id)
            if chat.invite_link:
                return chat.invite_link
            
            # Если ссылки нет, пытаемся создать
            invite_link = await client.create_chat_invite_link(group_id)
            return invite_link.invite_link
            
        except Exception as e:
            logger.error(f"Ошибка получения ссылки для группы {group_id}: {e}")
            return None
    
    def reset_daily_stats(self):
        """Сброс дневной статистики (вызывать раз в день)"""
        for account in self.accounts:
            account.daily_invites_count = 0
        
        self.config_manager.save_accounts(self.accounts)
        logger.info("Дневная статистика аккаунтов сброшена")
    
    async def shutdown(self):
        """Завершение работы менеджера"""
        for client in self.clients.values():
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Ошибка при отключении клиента: {e}")
        
        self.clients.clear()
        logger.info("Все клиенты отключены")
    
    def get_account_stats(self) -> Dict:
        """Получение статистики аккаунтов"""
        total_accounts = len(self.accounts)
        active_accounts = len([acc for acc in self.accounts if acc.is_active])
        total_daily_invites = sum(acc.daily_invites_count for acc in self.accounts)
        
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_daily_invites": total_daily_invites,
            "accounts_details": [
                {
                    "session_name": acc.session_name,
                    "phone": acc.phone,
                    "is_active": acc.is_active,
                    "daily_invites": acc.daily_invites_count,
                    "last_used": acc.last_used
                }
                for acc in self.accounts
            ]
        }
    
    async def test_account_connection(self, session_name: str) -> bool:
        """Тестирование подключения аккаунта"""
        client = self.clients.get(session_name)
        if not client:
            return False
        
        try:
            me = await client.get_me()
            logger.info(f"Тест подключения {session_name}: OK ({me.first_name})")
            return True
        except Exception as e:
            logger.error(f"Тест подключения {session_name}: FAILED ({e})")
            return False