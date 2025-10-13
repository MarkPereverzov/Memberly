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
class InvitationRecord:
    """Invitation record data"""
    id: Optional[int]
    user_id: int
    group_id: int
    group_name: str
    invitation_date: float
    success: bool
    error_message: Optional[str] = None

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
    
    def __init__(self, db_path: str = "data/bot_database.db"):
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
                
                # Create invitation records table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS invitation_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        group_name TEXT NOT NULL,
                        invitation_date REAL NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT
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
                
                # Create indexes for better performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_whitelist_expiration 
                    ON whitelist(expiration_date)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_invitation_user_date 
                    ON invitation_records(user_id, invitation_date)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_invitation_group_date 
                    ON invitation_records(group_id, invitation_date)
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
    
    # Invitation records methods
    def record_invitation(self, user_id: int, group_id: int, group_name: str, 
                         success: bool, error_message: Optional[str] = None) -> bool:
        """Record invitation attempt"""
        try:
            invitation_date = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO invitation_records 
                    (user_id, group_id, group_name, invitation_date, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, group_id, group_name, invitation_date, success, error_message))
                
                conn.commit()
                logger.debug(f"Recorded invitation: user {user_id} to group {group_name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error recording invitation: {e}")
            return False
    
    def get_user_invitation_history(self, user_id: int, limit: int = 50) -> List[InvitationRecord]:
        """Get user's invitation history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, user_id, group_id, group_name, invitation_date, success, error_message
                    FROM invitation_records 
                    WHERE user_id = ? 
                    ORDER BY invitation_date DESC 
                    LIMIT ?
                ''', (user_id, limit))
                
                results = cursor.fetchall()
                return [InvitationRecord(*row) for row in results]
                
        except sqlite3.Error as e:
            logger.error(f"Error getting user invitation history: {e}")
            return []
    
    def get_group_invitation_stats(self, group_id: int, days: int = 30) -> Dict:
        """Get invitation statistics for a group"""
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total invitations
                cursor.execute('''
                    SELECT COUNT(*) FROM invitation_records 
                    WHERE group_id = ? AND invitation_date >= ?
                ''', (group_id, cutoff_time))
                total_invitations = cursor.fetchone()[0]
                
                # Successful invitations
                cursor.execute('''
                    SELECT COUNT(*) FROM invitation_records 
                    WHERE group_id = ? AND invitation_date >= ? AND success = 1
                ''', (group_id, cutoff_time))
                successful_invitations = cursor.fetchone()[0]
                
                success_rate = (successful_invitations / total_invitations * 100) if total_invitations > 0 else 0
                
                return {
                    "total_invitations": total_invitations,
                    "successful_invitations": successful_invitations,
                    "failed_invitations": total_invitations - successful_invitations,
                    "success_rate": round(success_rate, 2),
                    "period_days": days
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting group invitation stats: {e}")
            return {"total_invitations": 0, "successful_invitations": 0, 
                   "failed_invitations": 0, "success_rate": 0, "period_days": days}
    
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
                
                # Total invitations (last 30 days)
                cutoff_time = time.time() - (30 * 24 * 60 * 60)
                cursor.execute('''
                    SELECT COUNT(*) FROM invitation_records 
                    WHERE invitation_date >= ?
                ''', (cutoff_time,))
                total_invitations_30d = cursor.fetchone()[0]
                
                # Successful invitations (last 30 days)
                cursor.execute('''
                    SELECT COUNT(*) FROM invitation_records 
                    WHERE invitation_date >= ? AND success = 1
                ''', (cutoff_time,))
                successful_invitations_30d = cursor.fetchone()[0]
                
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
                
                success_rate = (successful_invitations_30d / total_invitations_30d * 100) if total_invitations_30d > 0 else 0
                
                return {
                    "active_whitelist_users": active_whitelist,
                    "total_invitations_30d": total_invitations_30d,
                    "successful_invitations_30d": successful_invitations_30d,
                    "success_rate_30d": round(success_rate, 2),
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
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            cleanup_stats = {"invitation_records": 0}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up old invitation records
                cursor.execute('''
                    DELETE FROM invitation_records WHERE invitation_date < ?
                ''', (cutoff_time,))
                cleanup_stats["invitation_records"] = cursor.rowcount
                
                conn.commit()
                
                total_cleaned = sum(cleanup_stats.values())
                if total_cleaned > 0:
                    logger.info(f"Cleaned up {total_cleaned} old records")
                
                return cleanup_stats
                
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up old records: {e}")
            return {"invitation_records": 0}
    
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
        """Remove group from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
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