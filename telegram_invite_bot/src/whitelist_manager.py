"""
Whitelist manager for user access control
"""
import logging
import time
from typing import List, Optional, Dict, Set
from .database_manager import DatabaseManager, WhitelistEntry

logger = logging.getLogger(__name__)

class WhitelistManager:
    """Manager for user whitelist and access control"""
    
    def __init__(self, database_manager: DatabaseManager, admin_user_ids: List[int]):
        self.db = database_manager
        self.admin_user_ids = set(admin_user_ids)
        self._cache: Dict[int, bool] = {}  # Simple cache for performance
        self._cache_expiry = 0
        self._cache_duration = 300  # 5 minutes
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator"""
        return user_id in self.admin_user_ids
    
    def add_admin(self, user_id: int) -> bool:
        """Add user as administrator"""
        if user_id not in self.admin_user_ids:
            self.admin_user_ids.add(user_id)
            logger.info(f"Added admin: {user_id}")
            return True
        return False
    
    def remove_admin(self, user_id: int) -> bool:
        """Remove user as administrator"""
        if user_id in self.admin_user_ids:
            self.admin_user_ids.remove(user_id)
            logger.info(f"Removed admin: {user_id}")
            return True
        return False
    
    def get_admins(self) -> List[int]:
        """Get list of admin user IDs"""
        return list(self.admin_user_ids)
    
    def add_to_whitelist(self, user_id: int, days: int, added_by: int, 
                        username: Optional[str] = None) -> bool:
        """Add user to whitelist"""
        result = self.db.add_to_whitelist(user_id, days, added_by, username)
        if result:
            self._invalidate_cache()
        return result
    
    def remove_from_whitelist(self, user_id: int) -> bool:
        """Remove user from whitelist"""
        result = self.db.remove_from_whitelist(user_id)
        if result:
            self._invalidate_cache()
        return result
    
    def is_user_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted (with caching)"""
        # Always allow admins
        if self.is_admin(user_id):
            return True
        
        # Check cache first
        current_time = time.time()
        if current_time < self._cache_expiry and user_id in self._cache:
            return self._cache[user_id]
        
        # Query database
        result = self.db.is_user_whitelisted(user_id)
        
        # Update cache
        if current_time >= self._cache_expiry:
            self._cache.clear()
            self._cache_expiry = current_time + self._cache_duration
        
        self._cache[user_id] = result
        return result
    
    def can_user_access(self, user_id: int) -> tuple[bool, str]:
        """Check if user can access bot features with detailed reason"""
        # Check if admin
        if self.is_admin(user_id):
            return True, "Administrator access"
        
        # Check whitelist
        if self.is_user_whitelisted(user_id):
            entry = self.db.get_whitelist_entry(user_id)
            if entry:
                remaining_days = (entry.expiration_date - time.time()) / (24 * 60 * 60)
                return True, f"Whitelisted (expires in {int(remaining_days)} days)"
            return True, "Whitelisted"
        
        return False, "Not whitelisted. Contact an administrator for access."
    
    def get_whitelist_entry(self, user_id: int) -> Optional[WhitelistEntry]:
        """Get whitelist entry for user"""
        return self.db.get_whitelist_entry(user_id)
    
    def get_all_whitelisted_users(self) -> List[WhitelistEntry]:
        """Get all whitelisted users"""
        return self.db.get_all_whitelisted_users()
    
    def get_active_whitelisted_users(self) -> List[WhitelistEntry]:
        """Get only active (non-expired) whitelisted users"""
        all_users = self.get_all_whitelisted_users()
        current_time = time.time()
        return [user for user in all_users 
                if user.is_active and user.expiration_date > current_time]
    
    def extend_whitelist(self, user_id: int, additional_days: int, extended_by: int) -> bool:
        """Extend user's whitelist period"""
        entry = self.get_whitelist_entry(user_id)
        if not entry:
            return False
        
        # Calculate new expiration (from current expiration, not current time)
        current_expiration = max(entry.expiration_date, time.time())
        new_expiration_time = current_expiration + (additional_days * 24 * 60 * 60)
        
        # Convert back to days from now for the database method
        days_from_now = (new_expiration_time - time.time()) / (24 * 60 * 60)
        
        result = self.db.add_to_whitelist(user_id, int(days_from_now), extended_by, entry.username)
        if result:
            self._invalidate_cache()
            logger.info(f"Extended whitelist for user {user_id} by {additional_days} days")
        
        return result
    
    def get_expiring_users(self, days_ahead: int = 7) -> List[WhitelistEntry]:
        """Get users whose whitelist will expire within specified days"""
        all_users = self.get_active_whitelisted_users()
        cutoff_time = time.time() + (days_ahead * 24 * 60 * 60)
        
        return [user for user in all_users if user.expiration_date <= cutoff_time]
    
    def cleanup_expired_whitelist(self) -> int:
        """Remove expired whitelist entries"""
        removed_count = self.db.cleanup_expired_whitelist()
        if removed_count > 0:
            self._invalidate_cache()
        return removed_count
    
    def get_whitelist_stats(self) -> Dict:
        """Get whitelist statistics"""
        all_users = self.get_all_whitelisted_users()
        active_users = self.get_active_whitelisted_users()
        expiring_soon = self.get_expiring_users(7)
        
        return {
            "total_users": len(all_users),
            "active_users": len(active_users),
            "expired_users": len(all_users) - len(active_users),
            "expiring_within_7_days": len(expiring_soon),
            "total_admins": len(self.admin_user_ids)
        }
    
    def search_whitelist(self, query: str) -> List[WhitelistEntry]:
        """Search whitelist by username or user ID"""
        all_users = self.get_all_whitelisted_users()
        query_lower = query.lower()
        
        results = []
        for user in all_users:
            # Search by user ID
            if str(user.user_id) == query:
                results.append(user)
                continue
            
            # Search by username
            if user.username and query_lower in user.username.lower():
                results.append(user)
        
        return results
    
    def _invalidate_cache(self):
        """Invalidate the whitelist cache"""
        self._cache.clear()
        self._cache_expiry = 0
    
    def get_user_access_info(self, user_id: int) -> Dict:
        """Get comprehensive access information for a user"""
        info = {
            "user_id": user_id,
            "is_admin": self.is_admin(user_id),
            "is_whitelisted": False,
            "is_active": False,
            "expiration_date": None,
            "days_remaining": 0,
            "added_by": None,
            "added_date": None,
            "access_level": "none"
        }
        
        if info["is_admin"]:
            info["access_level"] = "admin"
            info["is_whitelisted"] = True
            info["is_active"] = True
            return info
        
        entry = self.get_whitelist_entry(user_id)
        if entry:
            info["is_whitelisted"] = True
            info["expiration_date"] = entry.expiration_date
            info["added_by"] = entry.added_by
            info["added_date"] = entry.added_date
            
            current_time = time.time()
            if entry.is_active and entry.expiration_date > current_time:
                info["is_active"] = True
                info["days_remaining"] = int((entry.expiration_date - current_time) / (24 * 60 * 60))
                info["access_level"] = "whitelisted"
            else:
                info["access_level"] = "expired"
        
        return info