"""
Blacklist manager for handling blocked users
"""
import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from .database_manager import DatabaseManager, BlacklistEntry

logger = logging.getLogger(__name__)

class BlacklistManager:
    """Manager for blacklist operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_user(self, user_id: int, reason: str, added_by: int, 
                 username: Optional[str] = None) -> bool:
        """Add user to blacklist"""
        try:
            # Remove from whitelist if exists
            if self.db_manager.is_user_whitelisted(user_id):
                self.db_manager.remove_from_whitelist(user_id)
                logger.info(f"Removed user {user_id} from whitelist before adding to blacklist")
            
            success = self.db_manager.add_to_blacklist(user_id, reason, added_by, username)
            
            if success:
                logger.info(f"User {user_id} added to blacklist by {added_by}. Reason: {reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding user to blacklist: {e}")
            return False
    
    def remove_user(self, user_id: int) -> bool:
        """Remove user from blacklist"""
        try:
            success = self.db_manager.remove_from_blacklist(user_id)
            
            if success:
                logger.info(f"User {user_id} removed from blacklist")
            
            return success
            
        except Exception as e:
            logger.error(f"Error removing user from blacklist: {e}")
            return False
    
    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is blacklisted"""
        try:
            return self.db_manager.is_user_blacklisted(user_id)
        except Exception as e:
            logger.error(f"Error checking blacklist status: {e}")
            return False
    
    def get_user_info(self, user_id: int) -> Optional[BlacklistEntry]:
        """Get blacklist entry for user"""
        try:
            return self.db_manager.get_blacklist_entry(user_id)
        except Exception as e:
            logger.error(f"Error getting blacklist entry: {e}")
            return None
    
    def get_all_blocked_users(self) -> List[BlacklistEntry]:
        """Get all blacklisted users"""
        try:
            return self.db_manager.get_all_blacklisted_users()
        except Exception as e:
            logger.error(f"Error getting all blacklisted users: {e}")
            return []
    
    def update_user_reason(self, user_id: int, new_reason: str) -> bool:
        """Update blacklist reason for user"""
        try:
            success = self.db_manager.update_blacklist_entry(user_id, reason=new_reason)
            
            if success:
                logger.info(f"Updated blacklist reason for user {user_id}: {new_reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating blacklist reason: {e}")
            return False
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate blacklist entry (soft delete)"""
        try:
            success = self.db_manager.update_blacklist_entry(user_id, is_active=False)
            
            if success:
                logger.info(f"Deactivated blacklist entry for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deactivating blacklist entry: {e}")
            return False
    
    def reactivate_user(self, user_id: int) -> bool:
        """Reactivate blacklist entry"""
        try:
            success = self.db_manager.update_blacklist_entry(user_id, is_active=True)
            
            if success:
                logger.info(f"Reactivated blacklist entry for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reactivating blacklist entry: {e}")
            return False
    
    def can_user_be_invited(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user can be invited (not blacklisted)
        Returns (can_invite: bool, reason: str)
        """
        try:
            if self.is_user_blocked(user_id):
                entry = self.get_user_info(user_id)
                reason = f"User is blacklisted. Reason: {entry.reason}" if entry else "User is blacklisted"
                return False, reason
            
            return True, "User can be invited"
            
        except Exception as e:
            logger.error(f"Error checking invitation eligibility: {e}")
            return False, f"Error checking user status: {e}"
    
    def get_blacklist_statistics(self) -> Dict:
        """Get blacklist statistics"""
        try:
            all_users = self.get_all_blocked_users()
            active_users = [user for user in all_users if user.is_active]
            
            # Count by reason
            reason_counts = {}
            for user in active_users:
                reason = user.reason.lower()
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            # Recent additions (last 7 days)
            week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
            recent_additions = [user for user in active_users if user.added_date > week_ago]
            
            return {
                "total_blacklisted": len(all_users),
                "active_blacklisted": len(active_users),
                "inactive_blacklisted": len(all_users) - len(active_users),
                "recent_additions_7d": len(recent_additions),
                "top_reasons": dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            }
            
        except Exception as e:
            logger.error(f"Error getting blacklist statistics: {e}")
            return {
                "total_blacklisted": 0,
                "active_blacklisted": 0,
                "inactive_blacklisted": 0,
                "recent_additions_7d": 0,
                "top_reasons": {}
            }
    
    def search_blacklist(self, query: str) -> List[BlacklistEntry]:
        """Search blacklist by username or reason"""
        try:
            all_users = self.get_all_blocked_users()
            query_lower = query.lower()
            
            filtered_users = []
            for user in all_users:
                # Search in username
                if user.username and query_lower in user.username.lower():
                    filtered_users.append(user)
                    continue
                
                # Search in reason
                if query_lower in user.reason.lower():
                    filtered_users.append(user)
                    continue
                
                # Search by user_id
                if str(user.user_id) == query:
                    filtered_users.append(user)
            
            return filtered_users
            
        except Exception as e:
            logger.error(f"Error searching blacklist: {e}")
            return []
    
    def bulk_add_users(self, users_data: List[Dict], added_by: int) -> Tuple[int, int]:
        """
        Bulk add users to blacklist
        users_data: List of dicts with keys: user_id, username (optional), reason
        Returns: (success_count, error_count)
        """
        success_count = 0
        error_count = 0
        
        for user_data in users_data:
            try:
                user_id = user_data['user_id']
                reason = user_data['reason']
                username = user_data.get('username')
                
                if self.add_user(user_id, reason, added_by, username):
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Error adding user to blacklist in bulk operation: {e}")
                error_count += 1
        
        logger.info(f"Bulk blacklist operation completed: {success_count} success, {error_count} errors")
        return success_count, error_count
    
    def export_blacklist(self) -> List[Dict]:
        """Export blacklist to dict format"""
        try:
            all_users = self.get_all_blocked_users()
            
            export_data = []
            for user in all_users:
                export_data.append({
                    "user_id": user.user_id,
                    "username": user.username,
                    "reason": user.reason,
                    "added_by": user.added_by,
                    "added_date": user.added_date,
                    "is_active": user.is_active
                })
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting blacklist: {e}")
            return []
    
    def get_blacklist_summary(self) -> str:
        """Get formatted summary of blacklist"""
        try:
            # Get all active blacklisted users using database manager method
            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, reason, added_date 
                    FROM blacklist 
                    WHERE is_active = 1 
                    ORDER BY added_date DESC
                """)
                
                blacklisted_users = cursor.fetchall()
            
            stats = self.get_blacklist_statistics()
            
            # Build new format
            summary = "🔄 **Blacklist Information (Updated)**\n\n"
            
            if blacklisted_users:
                for user in blacklisted_users:
                    user_id, username, reason, added_date = user
                    username_display = f"@{username}" if username else f"User_{user_id}"
                    summary += f"🚫 {username_display} (ID: {user_id})\n"
            else:
                summary += "✅ No users currently blacklisted\n"
            
            summary += f"\n📈 **Update Summary:**\n"
            summary += f"• 📊 Total: {stats['active_blacklisted']}"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting blacklist summary: {e}")
            return "⚠️ Error getting blacklist summary"