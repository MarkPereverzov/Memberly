"""
Database manager for whitelist and statistics
"""
import sqlite3
import logging
import time
import os
import json
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class WhitelistEntry:
    """Whitelist entry data"""
    user_id: int
    username: Optional[str]
    expiration_date: float
    added_by: int
    added_date: float
    is_active: bool = True

@dataclass
class BlacklistEntry:
    """Blacklist entry data"""
    user_id: int
    username: Optional[str]
    reason: str
    added_by: int
    added_date: float
    is_active: bool = True

@dataclass
class AccountEntry:
    """Account entry data"""
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
@dataclass
class GroupEntry:
    """Group entry data"""
    group_id: int
    group_name: str
    invite_link: str
    is_active: bool = True
    assigned_accounts: List[str] = None
    member_count: int = 0
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.assigned_accounts is None:
            self.assigned_accounts = []

class DatabaseManager:
    """Database manager for persistent storage"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to telegram_invite_bot/data directory
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(script_dir, 'data')
            db_path = os.path.join(data_dir, "bot_database.db")
        
        self.db_path = db_path
        self.ensure_db_directory()
        self.init_database()
    
    def ensure_db_directory(self):
        """Ensure database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create whitelist table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS whitelist (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        expiration_date REAL NOT NULL,
                        added_by INTEGER NOT NULL,
                        added_date REAL NOT NULL,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Create blacklist table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS blacklist (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        reason TEXT NOT NULL,
                        added_by INTEGER NOT NULL,
                        added_date REAL NOT NULL,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Create groups table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id INTEGER PRIMARY KEY,
                        group_name TEXT NOT NULL,
                        invite_link TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        assigned_accounts TEXT DEFAULT '[]',
                        member_count INTEGER DEFAULT 0,
                        last_updated REAL DEFAULT 0
                    )
                ''')
                
                # Drop old group_statistics table if exists
                cursor.execute('DROP TABLE IF EXISTS group_statistics')
                
                # Add member_count and last_updated columns to groups table if they don't exist
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN member_count INTEGER DEFAULT 0')
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                try:
                    cursor.execute('ALTER TABLE groups ADD COLUMN last_updated REAL DEFAULT 0')
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                # Create accounts table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS accounts (
                        session_name TEXT PRIMARY KEY,
                        api_id INTEGER NOT NULL,
                        api_hash TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        groups_assigned TEXT DEFAULT '[]'
                    )
                ''')
                
                # Create users table for tracking user information
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT UNIQUE,
                        first_name TEXT,
                        last_name TEXT,
                        last_interaction REAL NOT NULL,
                        created_date REAL NOT NULL
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_whitelist_expiration 
                    ON whitelist(expiration_date)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_blacklist_user 
                    ON blacklist(user_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_users_username 
                    ON users(username)
                ''')
                
                conn.commit()
                
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    # Whitelist management methods
    def add_to_whitelist(self, user_id: int, days: int, added_by: int, 
                        username: Optional[str] = None) -> bool:
        """Add user to whitelist"""
        try:
            expiration_date = time.time() + (days * 24 * 60 * 60)
            added_date = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO whitelist 
                    (user_id, username, expiration_date, added_by, added_date, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (user_id, username, expiration_date, added_by, added_date))
                
                conn.commit()
                logger.info(f"Added user {user_id} to whitelist for {days} days")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error adding user to whitelist: {e}")
            return False
    
    def remove_from_whitelist(self, user_id: int) -> bool:
        """Remove user from whitelist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM whitelist WHERE user_id = ?', (user_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Removed user {user_id} from whitelist")
                    return True
                else:
                    logger.warning(f"User {user_id} not found in whitelist")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error removing user from whitelist: {e}")
            return False
    
    def is_user_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted and not expired"""
        try:
            current_time = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT expiration_date FROM whitelist 
                    WHERE user_id = ? AND is_active = 1 AND expiration_date > ?
                ''', (user_id, current_time))
                
                result = cursor.fetchone()
                return result is not None
                
        except sqlite3.Error as e:
            logger.error(f"Error checking whitelist status: {e}")
            return False
    
    def get_whitelist_entry(self, user_id: int) -> Optional[WhitelistEntry]:
        """Get whitelist entry for user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, expiration_date, added_by, added_date, is_active
                    FROM whitelist WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return WhitelistEntry(*result)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting whitelist entry: {e}")
            return None
    
    def get_all_whitelisted_users(self) -> List[WhitelistEntry]:
        """Get all whitelisted users"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, expiration_date, added_by, added_date, is_active
                    FROM whitelist ORDER BY added_date DESC
                ''')
                
                results = cursor.fetchall()
                return [WhitelistEntry(*row) for row in results]
                
        except sqlite3.Error as e:
            logger.error(f"Error getting whitelisted users: {e}")
            return []
    
    def cleanup_expired_whitelist(self) -> int:
        """Remove expired whitelist entries"""
        try:
            current_time = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM whitelist WHERE expiration_date <= ?
                ''', (current_time,))
                
                removed_count = cursor.rowcount
                conn.commit()
                
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} expired whitelist entries")
                
                return removed_count
                
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up expired whitelist: {e}")
            return 0
    
    # Blacklist management methods
    def add_to_blacklist(self, user_id: int, reason: str, added_by: int, 
                        username: Optional[str] = None) -> bool:
        """Add user to blacklist"""
        try:
            added_date = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO blacklist 
                    (user_id, username, reason, added_by, added_date, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (user_id, username, reason, added_by, added_date))
                
                conn.commit()
                logger.info(f"Added user {user_id} to blacklist. Reason: {reason}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error adding user to blacklist: {e}")
            return False
    
    def remove_from_blacklist(self, user_id: int) -> bool:
        """Remove user from blacklist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Removed user {user_id} from blacklist")
                    return True
                else:
                    logger.warning(f"User {user_id} not found in blacklist")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error removing user from blacklist: {e}")
            return False
    
    def is_user_blacklisted(self, user_id: int) -> bool:
        """Check if user is blacklisted"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id FROM blacklist 
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id,))
                
                result = cursor.fetchone()
                return result is not None
                
        except sqlite3.Error as e:
            logger.error(f"Error checking blacklist status: {e}")
            return False
    
    def get_blacklist_entry(self, user_id: int) -> Optional[BlacklistEntry]:
        """Get blacklist entry for user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, reason, added_by, added_date, is_active
                    FROM blacklist WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return BlacklistEntry(*result)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting blacklist entry: {e}")
            return None
    
    def get_all_blacklisted_users(self) -> List[BlacklistEntry]:
        """Get all blacklisted users"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, reason, added_by, added_date, is_active
                    FROM blacklist ORDER BY added_date DESC
                ''')
                
                results = cursor.fetchall()
                return [BlacklistEntry(*row) for row in results]
                
        except sqlite3.Error as e:
            logger.error(f"Error getting blacklisted users: {e}")
            return []
    
    def update_blacklist_entry(self, user_id: int, reason: Optional[str] = None, 
                              is_active: Optional[bool] = None) -> bool:
        """Update blacklist entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query based on provided parameters
                updates = []
                params = []
                
                if reason is not None:
                    updates.append("reason = ?")
                    params.append(reason)
                
                if is_active is not None:
                    updates.append("is_active = ?")
                    params.append(is_active)
                
                if not updates:
                    return False
                
                params.append(user_id)
                
                cursor.execute(f'''
                    UPDATE blacklist SET {', '.join(updates)}
                    WHERE user_id = ?
                ''', params)
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated blacklist entry for user {user_id}")
                    return True
                else:
                    logger.warning(f"User {user_id} not found in blacklist")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error updating blacklist entry: {e}")
            return False
    
    # Invitation records methods
    # Group statistics methods
    def update_group_member_count(self, group_id: int, member_count: int) -> bool:
        """Update group member count"""
        try:
            last_updated = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE groups SET member_count = ?, last_updated = ?
                    WHERE group_id = ?
                ''', (member_count, last_updated, group_id))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Updated member count for group {group_id}: {member_count} members")
                    return True
                else:
                    logger.warning(f"Group {group_id} not found for stats update")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error updating group member count: {e}")
            return False
    
    def get_group_member_count(self, group_id: int) -> Optional[int]:
        """Get group member count"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT member_count FROM groups WHERE group_id = ?
                ''', (group_id,))
                
                result = cursor.fetchone()
                return result[0] if result else None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting group member count: {e}")
            return None
    
    def get_overall_statistics(self) -> Dict:
        """Get overall bot statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Active whitelisted users
                current_time = time.time()
                cursor.execute('''
                    SELECT COUNT(*) FROM whitelist 
                    WHERE is_active = 1 AND expiration_date > ?
                ''', (current_time,))
                active_whitelist = cursor.fetchone()[0]
                
                # Active blacklisted users
                cursor.execute('''
                    SELECT COUNT(*) FROM blacklist 
                    WHERE is_active = 1
                ''')
                active_blacklist = cursor.fetchone()[0]
                
                # Total groups with stats
                cursor.execute('SELECT COUNT(*) FROM groups WHERE is_active = 1')
                total_groups = cursor.fetchone()[0]
                
                # Average member count
                cursor.execute('SELECT AVG(member_count) FROM groups WHERE is_active = 1 AND member_count > 0')
                avg_members = cursor.fetchone()[0] or 0
                
                # Largest group
                cursor.execute('''
                    SELECT group_name, member_count FROM groups 
                    WHERE is_active = 1
                    ORDER BY member_count DESC LIMIT 1
                ''')
                largest_group = cursor.fetchone()
                
                return {
                    "active_whitelist_users": active_whitelist,
                    "active_blacklist_users": active_blacklist,
                    "total_groups": total_groups,
                    "average_member_count": round(avg_members, 0),
                    "largest_group": {
                        "name": largest_group[0] if largest_group else "N/A",
                        "member_count": largest_group[1] if largest_group else 0
                    }
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting overall statistics: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 90) -> Dict[str, int]:
        """Clean up old records"""
        try:
            # Placeholder for future cleanup logic if needed
            cleanup_stats = {}
            
            with sqlite3.connect(self.db_path) as conn:
                conn.commit()
                
                total_cleaned = sum(cleanup_stats.values())
                if total_cleaned > 0:
                    logger.info(f"Cleaned up {total_cleaned} old records")
                
                return cleanup_stats
                
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up old records: {e}")
            return {}
    
    # Account management methods
    def add_account(self, session_name: str, api_id: int, api_hash: str, phone: str, 
                   is_active: bool = True, groups_assigned: List[int] = None) -> bool:
        """Add account to database"""
        try:
            import json
            groups_json = json.dumps(groups_assigned or [])
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO accounts 
                    (session_name, api_id, api_hash, phone, is_active, groups_assigned)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (session_name, api_id, api_hash, phone, is_active, groups_json))
                
                conn.commit()
                logger.info(f"Added account {session_name} to database")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error adding account to database: {e}")
            return False
    
    def get_account(self, session_name: str) -> Optional[AccountEntry]:
        """Get account by session name"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_name, api_id, api_hash, phone, is_active, groups_assigned
                    FROM accounts WHERE session_name = ?
                ''', (session_name,))
                
                result = cursor.fetchone()
                if result:
                    session_name, api_id, api_hash, phone, is_active, groups_assigned_json = result
                    groups_assigned = json.loads(groups_assigned_json)
                    return AccountEntry(session_name, api_id, api_hash, phone, bool(is_active), groups_assigned)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting account: {e}")
            return None
    
    def get_all_accounts(self) -> List[AccountEntry]:
        """Get all accounts"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_name, api_id, api_hash, phone, is_active, groups_assigned
                    FROM accounts ORDER BY session_name
                ''')
                
                results = cursor.fetchall()
                accounts = []
                for row in results:
                    session_name, api_id, api_hash, phone, is_active, groups_assigned_json = row
                    groups_assigned = json.loads(groups_assigned_json)
                    accounts.append(AccountEntry(session_name, api_id, api_hash, phone, bool(is_active), groups_assigned))
                
                return accounts
                
        except sqlite3.Error as e:
            logger.error(f"Error getting all accounts: {e}")
            return []
    
    def update_account(self, session_name: str, **kwargs) -> bool:
        """Update account parameters"""
        try:
            import json
            
            # Get current account data
            account = self.get_account(session_name)
            if not account:
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(account, key):
                    setattr(account, key, value)
            
            # Save back to database
            groups_json = json.dumps(account.groups_assigned)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accounts SET api_id = ?, api_hash = ?, phone = ?, 
                    is_active = ?, groups_assigned = ?
                    WHERE session_name = ?
                ''', (account.api_id, account.api_hash, account.phone, 
                     account.is_active, groups_json, session_name))
                
                conn.commit()
                logger.info(f"Updated account {session_name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error updating account: {e}")
            return False
    
    def remove_account(self, session_name: str) -> bool:
        """Remove account from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM accounts WHERE session_name = ?', (session_name,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Removed account {session_name}")
                    return True
                else:
                    logger.warning(f"Account {session_name} not found")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error removing account: {e}")
            return False
    
    # Group management methods
    def add_group(self, group_id: int, group_name: str, invite_link: str, 
                 is_active: bool = True, assigned_accounts: List[str] = None,
                 member_count: int = 0, last_updated: float = 0.0) -> bool:
        """Add group to database"""
        try:
            import json
            accounts_json = json.dumps(assigned_accounts or [])
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO groups 
                    (group_id, group_name, invite_link, is_active, assigned_accounts, member_count, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (group_id, group_name, invite_link, is_active, accounts_json, member_count, last_updated))
                
                conn.commit()
                logger.info(f"Added group {group_name} to database")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error adding group to database: {e}")
            return False
    
    def get_group(self, group_id: int) -> Optional[GroupEntry]:
        """Get group by ID"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT group_id, group_name, invite_link, is_active, assigned_accounts, member_count, last_updated
                    FROM groups WHERE group_id = ?
                ''', (group_id,))
                
                result = cursor.fetchone()
                if result:
                    group_id, group_name, invite_link, is_active, assigned_accounts_json, member_count, last_updated = result
                    assigned_accounts = json.loads(assigned_accounts_json)
                    return GroupEntry(group_id, group_name, invite_link, bool(is_active), assigned_accounts, member_count, last_updated)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting group: {e}")
            return None
    
    def get_all_groups(self) -> List[GroupEntry]:
        """Get all groups"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT group_id, group_name, invite_link, is_active, assigned_accounts, member_count, last_updated
                    FROM groups ORDER BY group_name
                ''')
                
                results = cursor.fetchall()
                groups = []
                for row in results:
                    group_id, group_name, invite_link, is_active, assigned_accounts_json, member_count, last_updated = row
                    assigned_accounts = json.loads(assigned_accounts_json)
                    groups.append(GroupEntry(group_id, group_name, invite_link, bool(is_active), assigned_accounts, member_count, last_updated))
                
                return groups
                
        except sqlite3.Error as e:
            logger.error(f"Error getting all groups: {e}")
            return []
    
    def update_group(self, group_id: int, **kwargs) -> bool:
        """Update group parameters"""
        try:
            import json
            
            # Get current group data
            group = self.get_group(group_id)
            if not group:
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(group, key):
                    setattr(group, key, value)
            
            # Save back to database
            accounts_json = json.dumps(group.assigned_accounts)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE groups SET group_name = ?, invite_link = ?, 
                    is_active = ?, assigned_accounts = ?, member_count = ?, last_updated = ?
                    WHERE group_id = ?
                ''', (group.group_name, group.invite_link, 
                     group.is_active, accounts_json, group.member_count, group.last_updated, group_id))
                
                conn.commit()
                logger.info(f"Updated group {group.group_name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error updating group: {e}")
            return False
    
    def remove_group(self, group_id: int) -> bool:
        """Remove group from database and all related records"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove group from groups table
                cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
                group_deleted = cursor.rowcount > 0
                
                conn.commit()
                
                if group_deleted:
                    logger.info(f"Removed group with ID {group_id}")
                    return True
                else:
                    logger.warning(f"Group with ID {group_id} not found")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error removing group: {e}")
            return False
    
    def migrate_from_json(self, accounts_data: List[Dict], groups_data: List[Dict]) -> bool:
        """Migrate data from JSON files to database"""
        try:
            # Migrate accounts
            for account_data in accounts_data:
                # Remove last_used field if present
                if 'last_used' in account_data:
                    del account_data['last_used']
                
                self.add_account(
                    account_data['session_name'],
                    account_data['api_id'],
                    account_data['api_hash'],
                    account_data['phone'],
                    account_data.get('is_active', True),
                    account_data.get('groups_assigned', [])
                )
            
            # Migrate groups
            for group_data in groups_data:
                self.add_group(
                    group_data['group_id'],
                    group_data['group_name'],
                    group_data['invite_link'],
                    group_data.get('is_active', True),
                    group_data.get('assigned_accounts', [])
                )
            
            logger.info(f"Migrated {len(accounts_data)} accounts and {len(groups_data)} groups to database")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating data: {e}")
            return False
    
    def update_user_info(self, user_id: int, username: str = None, 
                        first_name: str = None, last_name: str = None) -> bool:
        """Update or insert user information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone() is not None
                
                current_time = time.time()
                
                if exists:
                    # Update existing user
                    cursor.execute('''
                        UPDATE users 
                        SET username = COALESCE(?, username),
                            first_name = COALESCE(?, first_name),
                            last_name = COALESCE(?, last_name),
                            last_interaction = ?
                        WHERE user_id = ?
                    ''', (username, first_name, last_name, current_time, user_id))
                else:
                    # Insert new user
                    cursor.execute('''
                        INSERT INTO users (user_id, username, first_name, last_name, 
                                         last_interaction, created_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, first_name, last_name, current_time, current_time))
                
                conn.commit()
                logger.debug(f"Updated user info: {user_id} (@{username})")
                return True
                
        except Exception as e:
            logger.error(f"Error updating user info: {e}")
            return False
    
    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Get user_id by username"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove @ if present
                clean_username = username.replace('@', '') if username.startswith('@') else username
                
                cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                return None
                
        except Exception as e:
            logger.error(f"Error getting user_id for username {username}: {e}")
            return None
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Get user information by user_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, 
                           last_interaction, created_date
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'username': result[1],
                        'first_name': result[2],
                        'last_name': result[3],
                        'last_interaction': result[4],
                        'created_date': result[5]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {e}")
            return None