"""
Конфигурация для бота-приглашающего
"""
import os
from dataclasses import dataclass
from typing import List, Dict
import json

@dataclass
class BotConfig:
    """Основная конфигурация бота"""
    bot_token: str
    admin_user_ids: List[int]
    whitelist_user_ids: List[int]
    invite_cooldown_seconds: int = 300  # 5 минут между приглашениями
    group_cooldown_seconds: int = 60    # 1 минута между приглашениями в разные группы
    max_invites_per_day: int = 50       # Максимум приглашений в день на пользователя
    
    @classmethod
    def from_env(cls):
        """Загрузка конфигурации из переменных окружения"""
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")
        
        admin_ids = os.getenv('ADMIN_USER_IDS', '').split(',')
        admin_user_ids = [int(id.strip()) for id in admin_ids if id.strip().isdigit()]
        
        whitelist_ids = os.getenv('WHITELIST_USER_IDS', '').split(',')
        whitelist_user_ids = [int(id.strip()) for id in whitelist_ids if id.strip().isdigit()]
        
        return cls(
            bot_token=bot_token,
            admin_user_ids=admin_user_ids,
            whitelist_user_ids=whitelist_user_ids,
            invite_cooldown_seconds=int(os.getenv('INVITE_COOLDOWN_SECONDS', 300)),
            group_cooldown_seconds=int(os.getenv('GROUP_COOLDOWN_SECONDS', 60)),
            max_invites_per_day=int(os.getenv('MAX_INVITES_PER_DAY', 50))
        )

@dataclass
class UserAccount:
    """Конфигурация пользовательского аккаунта Telegram"""
    session_name: str
    api_id: int
    api_hash: str
    phone: str
    is_active: bool = True
    last_used: float = 0.0
    daily_invites_count: int = 0
    groups_assigned: List[int] = None
    
    def __post_init__(self):
        if self.groups_assigned is None:
            self.groups_assigned = []

@dataclass
class TelegramGroup:
    """Конфигурация группы Telegram"""
    group_id: int
    group_name: str
    invite_link: str
    is_active: bool = True
    assigned_accounts: List[str] = None  # session_names аккаунтов
    max_daily_invites: int = 100
    current_daily_invites: int = 0
    
    def __post_init__(self):
        if self.assigned_accounts is None:
            self.assigned_accounts = []

class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.accounts_file = os.path.join(config_dir, "accounts.json")
        self.groups_file = os.path.join(config_dir, "groups.json")
        self.bot_config = BotConfig.from_env()
        
    def load_accounts(self) -> List[UserAccount]:
        """Загрузка пользовательских аккаунтов"""
        if not os.path.exists(self.accounts_file):
            return []
        
        with open(self.accounts_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        accounts = []
        for account_data in data:
            accounts.append(UserAccount(**account_data))
        
        return accounts
    
    def save_accounts(self, accounts: List[UserAccount]):
        """Сохранение пользовательских аккаунтов"""
        data = []
        for account in accounts:
            account_dict = {
                'session_name': account.session_name,
                'api_id': account.api_id,
                'api_hash': account.api_hash,
                'phone': account.phone,
                'is_active': account.is_active,
                'last_used': account.last_used,
                'daily_invites_count': account.daily_invites_count,
                'groups_assigned': account.groups_assigned
            }
            data.append(account_dict)
        
        with open(self.accounts_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_groups(self) -> List[TelegramGroup]:
        """Загрузка групп"""
        if not os.path.exists(self.groups_file):
            return []
        
        with open(self.groups_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        groups = []
        for group_data in data:
            groups.append(TelegramGroup(**group_data))
        
        return groups
    
    def save_groups(self, groups: List[TelegramGroup]):
        """Сохранение групп"""
        data = []
        for group in groups:
            group_dict = {
                'group_id': group.group_id,
                'group_name': group.group_name,
                'invite_link': group.invite_link,
                'is_active': group.is_active,
                'assigned_accounts': group.assigned_accounts,
                'max_daily_invites': group.max_daily_invites,
                'current_daily_invites': group.current_daily_invites
            }
            data.append(group_dict)
        
        with open(self.groups_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_account(self, session_name: str, api_id: int, api_hash: str, phone: str):
        """Добавление нового аккаунта"""
        accounts = self.load_accounts()
        
        # Проверяем, что такого аккаунта еще нет
        for account in accounts:
            if account.session_name == session_name:
                raise ValueError(f"Аккаунт с именем сессии '{session_name}' уже существует")
        
        new_account = UserAccount(
            session_name=session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone
        )
        
        accounts.append(new_account)
        self.save_accounts(accounts)
        
        return new_account
    
    def add_group(self, group_id: int, group_name: str, invite_link: str):
        """Добавление новой группы"""
        groups = self.load_groups()
        
        # Проверяем, что такой группы еще нет
        for group in groups:
            if group.group_id == group_id:
                raise ValueError(f"Группа с ID '{group_id}' уже существует")
        
        new_group = TelegramGroup(
            group_id=group_id,
            group_name=group_name,
            invite_link=invite_link
        )
        
        groups.append(new_group)
        self.save_groups(groups)
        
        return new_group