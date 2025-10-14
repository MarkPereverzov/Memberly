"""
Configuration for invite bot
"""
import os
from dataclasses import dataclass
from typing import List, Dict
import json

@dataclass
class BotConfig:
    """Main bot configuration"""
    bot_token: str
    admin_user_ids: List[int]
    whitelist_user_ids: List[int]
    invite_cooldown_seconds: int = 180  # 3 minutes between invitations (from .env)
    group_cooldown_seconds: int = 3     # 3 seconds between invitations to different groups (from .env)
    
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            raise ValueError("BOT_TOKEN not found in environment variables")
        
        admin_ids = os.getenv('ADMIN_USER_IDS', '').split(',')
        admin_user_ids = [int(id.strip()) for id in admin_ids if id.strip().isdigit()]
        
        whitelist_ids = os.getenv('WHITELIST_USER_IDS', '').split(',')
        whitelist_user_ids = [int(id.strip()) for id in whitelist_ids if id.strip().isdigit()]
        
        return cls(
            bot_token=bot_token,
            admin_user_ids=admin_user_ids,
            whitelist_user_ids=whitelist_user_ids,
            invite_cooldown_seconds=int(os.getenv('INVITE_COOLDOWN_SECONDS', 180)),
            group_cooldown_seconds=int(os.getenv('GROUP_COOLDOWN_SECONDS', 3))
        )

@dataclass
class UserAccount:
    """Telegram user account configuration"""
    session_name: str
    api_id: int
    api_hash: str
    phone: str
    is_active: bool = True
    groups_assigned: List[int] = None
    
    def __post_init__(self):
        if self.groups_assigned is None:
            self.groups_assigned = []

@dataclass
class TelegramGroup:
    """Telegram group configuration"""
    group_id: int
    group_name: str
    invite_link: str
    is_active: bool = True
    assigned_accounts: List[str] = None  # session_names of accounts
    member_count: int = 0
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.assigned_accounts is None:
            self.assigned_accounts = []

class ConfigManager:
    """Configuration manager"""
    
    def __init__(self, config_dir: str = "config", db_path: str = None):
        if db_path is None:
            # Default to project root data directory  
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(script_dir, '..', 'data')
            db_path = os.path.join(data_dir, "bot_database.db")
            
        self.config_dir = config_dir
        self.db_path = db_path
        self.bot_config = BotConfig.from_env()
        
        # Import here to avoid circular imports
        from src.database_manager import DatabaseManager
        self.db = DatabaseManager(db_path)
        
    def load_accounts(self) -> List[UserAccount]:
        """Load user accounts from database"""
        try:
            db_accounts = self.db.get_all_accounts()
            accounts = []
            
            for db_account in db_accounts:
                account = UserAccount(
                    session_name=db_account.session_name,
                    api_id=db_account.api_id,
                    api_hash=db_account.api_hash,
                    phone=db_account.phone,
                    is_active=db_account.is_active,
                    groups_assigned=db_account.groups_assigned
                )
                accounts.append(account)
            
            return accounts
            
        except Exception as e:
            # Fallback to JSON file if database fails
            accounts_file = os.path.join(self.config_dir, "accounts.json")
            if os.path.exists(accounts_file):
                with open(accounts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                accounts = []
                for account_data in data:
                    # Remove last_used if present
                    if 'last_used' in account_data:
                        del account_data['last_used']
                    accounts.append(UserAccount(**account_data))
                
                return accounts
            
            return []
    
    def save_accounts(self, accounts: List[UserAccount]):
        """Save user accounts to database"""
        try:
            for account in accounts:
                self.db.add_account(
                    account.session_name,
                    account.api_id,
                    account.api_hash,
                    account.phone,
                    account.is_active,
                    account.groups_assigned
                )
        except Exception as e:
            # Fallback to JSON file if database fails
            accounts_file = os.path.join(self.config_dir, "accounts.json")
            data = []
            for account in accounts:
                account_dict = {
                    'session_name': account.session_name,
                    'api_id': account.api_id,
                    'api_hash': account.api_hash,
                    'phone': account.phone,
                    'is_active': account.is_active,
                    'groups_assigned': account.groups_assigned
                }
                data.append(account_dict)
            
            with open(accounts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_groups(self) -> List[TelegramGroup]:
        """Load groups from database"""
        try:
            db_groups = self.db.get_all_groups()
            groups = []
            
            for db_group in db_groups:
                group = TelegramGroup(
                    group_id=db_group.group_id,
                    group_name=db_group.group_name,
                    invite_link=db_group.invite_link,
                    is_active=db_group.is_active,
                    assigned_accounts=db_group.assigned_accounts,
                    member_count=getattr(db_group, 'member_count', 0),
                    last_updated=getattr(db_group, 'last_updated', 0.0)
                )
                groups.append(group)
            
            return groups
            
        except Exception as e:
            # Fallback to JSON file if database fails
            groups_file = os.path.join(self.config_dir, "groups.json")
            if os.path.exists(groups_file):
                with open(groups_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                groups = []
                for group_data in data:
                    groups.append(TelegramGroup(**group_data))
                
                return groups
            
            return []
    
    def save_groups(self, groups: List[TelegramGroup]):
        """Save groups to database"""
        try:
            for group in groups:
                self.db.add_group(
                    group.group_id,
                    group.group_name,
                    group.invite_link,
                    group.is_active,
                    group.assigned_accounts
                )
        except Exception as e:
            # Fallback to JSON file if database fails
            groups_file = os.path.join(self.config_dir, "groups.json")
            data = []
            for group in groups:
                group_dict = {
                    'group_id': group.group_id,
                    'group_name': group.group_name,
                    'invite_link': group.invite_link,
                    'is_active': group.is_active,
                    'assigned_accounts': group.assigned_accounts
                }
                data.append(group_dict)
            
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_account(self, session_name: str, api_id: int, api_hash: str, phone: str):
        """Add new account"""
        # Check that such account doesn't exist yet
        existing_account = self.db.get_account(session_name)
        if existing_account:
            raise ValueError(f"Account with session name '{session_name}' already exists")
        
        new_account = UserAccount(
            session_name=session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone
        )
        
        # Add to database
        success = self.db.add_account(
            session_name=session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            is_active=True,
            groups_assigned=[]
        )
        
        if not success:
            raise ValueError(f"Failed to add account '{session_name}' to database")
        
        return new_account
    
    def add_group(self, group_id: int, group_name: str, invite_link: str):
        """Add new group"""
        # Check that such group doesn't exist yet
        existing_group = self.db.get_group(group_id)
        if existing_group:
            raise ValueError(f"Group with ID '{group_id}' already exists")
        
        new_group = TelegramGroup(
            group_id=group_id,
            group_name=group_name,
            invite_link=invite_link
        )
        
        # Add to database
        success = self.db.add_group(
            group_id=group_id,
            group_name=group_name,
            invite_link=invite_link,
            is_active=True,
            assigned_accounts=[]
        )
        
        if not success:
            raise ValueError(f"Failed to add group '{group_name}' to database")
        
        return new_group