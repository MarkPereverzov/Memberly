"""
Cooldown system and ban protection
"""
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class CooldownRecord:
    """Cooldown record"""
    user_id: int
    last_invite_time: float
    blocked_until: Optional[float] = None

class CooldownManager:
    """Cooldown and spam protection manager"""
    
    def __init__(self, data_dir: str = "data", config=None):
        self.data_dir = data_dir
        self.cooldowns_file = os.path.join(data_dir, "cooldowns.json")
        self.user_cooldowns: Dict[int, CooldownRecord] = {}
        self.group_last_invite: Dict[int, float] = {}  # group_id -> timestamp
        
        # Cooldown settings - use config if provided, otherwise defaults
        if config:
            self.invite_cooldown_seconds = config.invite_cooldown_seconds
            self.group_cooldown_seconds = config.group_cooldown_seconds  
        else:
            self.invite_cooldown_seconds = 180  # 3 minutes between invitations (default)
            self.group_cooldown_seconds = 3     # 3 seconds between group invitations (default)
        
        self.ban_duration_hours = 24        # Ban duration in hours
        
        self.load_cooldowns()
    
    def load_cooldowns(self):
        """Load cooldown data"""
        if not os.path.exists(self.cooldowns_file):
            return
        
        try:
            with open(self.cooldowns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for user_id_str, record_data in data.items():
                user_id = int(user_id_str)
                self.user_cooldowns[user_id] = CooldownRecord(**record_data)
                
            logger.info(f"Loaded {len(self.user_cooldowns)} cooldown records")
            
        except Exception as e:
            logger.error(f"Error loading cooldowns: {e}")
    
    def save_cooldowns(self):
        """Save cooldown data"""
        try:
            data = {}
            for user_id, record in self.user_cooldowns.items():
                data[str(user_id)] = {
                    'user_id': record.user_id,
                    'last_invite_time': record.last_invite_time,
                    'last_reset_date': record.last_reset_date,
                    'blocked_until': record.blocked_until
                }
            
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.cooldowns_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving cooldowns: {e}")
    
    def can_user_request_invite(self, user_id: int) -> tuple[bool, str]:
        """Check if user can request an invitation"""
        current_time = time.time()
        today = time.strftime("%Y-%m-%d")
        
        # Get or create user record
        if user_id not in self.user_cooldowns:
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=0,
                last_reset_date=today
            )
        
        record = self.user_cooldowns[user_id]
        
        # Check if blocked
        if record.blocked_until and current_time < record.blocked_until:
            remaining_time = int(record.blocked_until - current_time)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            return False, f"You are blocked until {time.strftime('%H:%M %d.%m.%Y', time.localtime(record.blocked_until))} ({hours}h {minutes}m remaining)"
        
        # Reset blocked status if new day
        if record.last_reset_date != today:
            record.last_reset_date = today
            record.blocked_until = None
        
        # Check cooldown between invitations
        time_since_last = current_time - record.last_invite_time
        if time_since_last < self.invite_cooldown_seconds:
            remaining_cooldown = int(self.invite_cooldown_seconds - time_since_last)
            minutes = remaining_cooldown // 60
            seconds = remaining_cooldown % 60
            return False, f"Please wait {minutes}m {seconds}s before the next invitation."
        
        return True, "OK"
    
    def can_user_request_invite_simple(self, user_id: int) -> tuple[bool, str]:
        """Check if user can request an invitation (without daily limits)"""
        current_time = time.time()
        today = time.strftime("%Y-%m-%d")
        
        # Get or create user record
        if user_id not in self.user_cooldowns:
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=0,
                last_reset_date=today
            )
        
        record = self.user_cooldowns[user_id]
        
        # Check if blocked
        if record.blocked_until and current_time < record.blocked_until:
            remaining_time = int(record.blocked_until - current_time)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            return False, f"You are blocked until {time.strftime('%H:%M %d.%m.%Y', time.localtime(record.blocked_until))} ({hours}h {minutes}m remaining)"
        
        # Reset blocked status if new day
        if record.last_reset_date != today:
            record.last_reset_date = today
            record.blocked_until = None
        
        # Only check cooldown between invitations (no daily limit)
        time_since_last = current_time - record.last_invite_time
        if time_since_last < self.invite_cooldown_seconds:
            remaining_cooldown = int(self.invite_cooldown_seconds - time_since_last)
            minutes = remaining_cooldown // 60
            seconds = remaining_cooldown % 60
            return False, f"Please wait {minutes}m {seconds}s before the next invitation."
        
        return True, "OK"
    
    def can_invite_to_group(self, group_id: int) -> tuple[bool, str]:
        """Check if invitation can be sent to group"""
        current_time = time.time()
        
        if group_id in self.group_last_invite:
            time_since_last = current_time - self.group_last_invite[group_id]
            if time_since_last < self.group_cooldown_seconds:
                remaining_cooldown = int(self.group_cooldown_seconds - time_since_last)
                return False, f"Group cooldown: wait {remaining_cooldown}s"
        
        return True, "OK"
    
    def record_invite_attempt(self, user_id: int, group_id: int, success: bool):
        """Record invitation attempt"""
        current_time = time.time()
        
        # Update user record
        if user_id in self.user_cooldowns:
            record = self.user_cooldowns[user_id]
            record.last_invite_time = current_time
        
        # Update last invitation time to group
        if success:
            self.group_last_invite[group_id] = current_time
        
        self.save_cooldowns()
    
    def update_user_last_invite_time(self, user_id: int):
        """Update user's last invite time (for multi-group invitations)"""
        current_time = time.time()
        today = time.strftime("%Y-%m-%d")
        
        # Get or create user record
        if user_id not in self.user_cooldowns:
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=current_time,
                last_reset_date=today
            )
        else:
            self.user_cooldowns[user_id].last_invite_time = current_time
        
        self.save_cooldowns()
    
    def block_user(self, user_id: int, duration_hours: Optional[int] = None):
        """Block user"""
        if duration_hours is None:
            duration_hours = self.ban_duration_hours
        
        current_time = time.time()
        block_until = current_time + (duration_hours * 3600)
        
        if user_id not in self.user_cooldowns:
            today = time.strftime("%Y-%m-%d")
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=current_time,
                last_reset_date=today
            )
        
        self.user_cooldowns[user_id].blocked_until = block_until
        self.save_cooldowns()
        
        logger.warning(f"User {user_id} blocked for {duration_hours} hours")
    
    def unblock_user(self, user_id: int):
        """Unblock user"""
        if user_id in self.user_cooldowns:
            self.user_cooldowns[user_id].blocked_until = None
            self.save_cooldowns()
            logger.info(f"User {user_id} unblocked")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        if user_id not in self.user_cooldowns:
            return {
                "last_invite_time": 0,
                "is_blocked": False,
                "blocked_until": None,
                "can_invite": True
            }
        
        record = self.user_cooldowns[user_id]
        current_time = time.time()
        
        is_blocked = record.blocked_until and current_time < record.blocked_until
        can_invite, _ = self.can_user_request_invite_simple(user_id)
        
        return {
            "last_invite_time": record.last_invite_time,
            "is_blocked": is_blocked,
            "blocked_until": record.blocked_until,
            "can_invite": can_invite
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        today = time.strftime("%Y-%m-%d")
        
        for record in self.user_cooldowns.values():
            record.last_reset_date = today
            # Don't reset blocks - they should expire naturally
        
        self.save_cooldowns()
        logger.info("Daily cooldown statistics reset")
    
    def cleanup_expired_blocks(self):
        """Clean up expired blocks"""
        current_time = time.time()
        cleaned_count = 0
        
        for record in self.user_cooldowns.values():
            if record.blocked_until and current_time >= record.blocked_until:
                record.blocked_until = None
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.save_cooldowns()
            logger.info(f"Cleaned up {cleaned_count} expired blocks")
    
    def get_global_stats(self) -> Dict:
        """Get global statistics"""
        current_time = time.time()
        
        total_users = len(self.user_cooldowns)
        active_blocks = sum(1 for r in self.user_cooldowns.values() 
                           if r.blocked_until and current_time < r.blocked_until)
        
        return {
            "total_users": total_users,
            "active_blocks": active_blocks,
            "invite_cooldown_seconds": self.invite_cooldown_seconds,
            "group_cooldown_seconds": self.group_cooldown_seconds
        }
    
    def update_settings(self, invite_cooldown: Optional[int] = None, 
                       group_cooldown: Optional[int] = None):
        """Update cooldown settings"""
        if invite_cooldown is not None:
            self.invite_cooldown_seconds = invite_cooldown
        
        if group_cooldown is not None:
            self.group_cooldown_seconds = group_cooldown
        
        logger.info("Cooldown settings updated")
    
    def get_recent_activity(self, hours: int = 24) -> List[Dict]:
        """Get recent activity"""
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        recent_activity = []
        for record in self.user_cooldowns.values():
            if record.last_invite_time >= cutoff_time:
                recent_activity.append({
                    "user_id": record.user_id,
                    "last_invite_time": record.last_invite_time,
                    "is_blocked": record.blocked_until and current_time < record.blocked_until
                })
        
        # Sort by last invitation time
        recent_activity.sort(key=lambda x: x["last_invite_time"], reverse=True)
        
        return recent_activity