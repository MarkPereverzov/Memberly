"""
Group manager for the invitation bot
"""
import logging
import time
from typing import List, Optional, Dict, Set
from config.config import TelegramGroup, ConfigManager

logger = logging.getLogger(__name__)

class GroupManager:
    """Manager for target groups for invitations"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.groups: List[TelegramGroup] = []
        self.user_invitations: Dict[int, Dict[int, float]] = {}  # user_id -> {group_id: timestamp}
        
    def initialize(self):
        """Initialize the group manager"""
        self.groups = self.config_manager.load_groups()
        logger.info(f"Loaded {len(self.groups)} groups")
    
    def get_available_groups_for_user(self, user_id: int) -> List[TelegramGroup]:
        """Get list of groups to which the user has not been invited yet"""
        available_groups = []
        user_invites = self.user_invitations.get(user_id, {})
        
        for group in self.groups:
            if not group.is_active:
                continue
                
            # Check if daily invitation limit for the group has been reached
            if group.current_daily_invites >= group.max_daily_invites:
                continue
                
            # Check if the user has already been invited to this group
            if group.group_id in user_invites:
                # Check cooldown (e.g., 24 hours)
                last_invite_time = user_invites[group.group_id]
                if time.time() - last_invite_time < 24 * 60 * 60:  # 24 hours
                    continue
            
            available_groups.append(group)
        
        return available_groups
    
    def get_group_by_id(self, group_id: int) -> Optional[TelegramGroup]:
        """Get group by ID"""
        for group in self.groups:
            if group.group_id == group_id:
                return group
        return None
    
    def get_active_groups(self) -> List[TelegramGroup]:
        """Get all active groups"""
        return [group for group in self.groups if group.is_active]
    
    def select_best_group_for_user(self, user_id: int) -> Optional[TelegramGroup]:
        """Select the best group for user invitation"""
        available_groups = self.get_available_groups_for_user(user_id)
        
        if not available_groups:
            return None
        
        # Sort groups by invitation count (fewer invitations = higher priority)
        available_groups.sort(key=lambda x: x.current_daily_invites)
        
        return available_groups[0]
    
    def record_invitation(self, user_id: int, group_id: int) -> bool:
        """Record user invitation to group"""
        group = self.get_group_by_id(group_id)
        if not group:
            logger.error(f"Group with ID {group_id} not found")
            return False
        
        # Record the invitation
        if user_id not in self.user_invitations:
            self.user_invitations[user_id] = {}
        
        self.user_invitations[user_id][group_id] = time.time()
        
        # Increment invitation counter for the group
        group.current_daily_invites += 1
        
        # Save changes
        self.config_manager.save_groups(self.groups)
        
        logger.info(f"Recorded invitation of user {user_id} to group {group.group_name}")
        return True
    
    def check_group_cooldown(self, group_id: int, cooldown_seconds: int = 60) -> bool:
        """Check group cooldown"""
        # This can be extended to track the last invitation to each group
        # For now, return True (cooldown has passed)
        return True
    
    def get_groups_by_account(self, session_name: str) -> List[TelegramGroup]:
        """Get groups assigned to a specific account"""
        assigned_groups = []
        for group in self.groups:
            if session_name in group.assigned_accounts:
                assigned_groups.append(group)
        return assigned_groups
    
    def assign_account_to_group(self, session_name: str, group_id: int) -> bool:
        """Assign account to group"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        if session_name not in group.assigned_accounts:
            group.assigned_accounts.append(session_name)
            self.config_manager.save_groups(self.groups)
            logger.info(f"Account {session_name} assigned to group {group.group_name}")
        
        return True
    
    def remove_account_from_group(self, session_name: str, group_id: int) -> bool:
        """Remove account from group"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        if session_name in group.assigned_accounts:
            group.assigned_accounts.remove(session_name)
            self.config_manager.save_groups(self.groups)
            logger.info(f"Account {session_name} removed from group {group.group_name}")
        
        return True
    
    def reset_daily_stats(self):
        """Reset daily group statistics"""
        for group in self.groups:
            group.current_daily_invites = 0
        
        self.config_manager.save_groups(self.groups)
        logger.info("Daily group statistics reset")
    
    def get_group_stats(self) -> Dict:
        """Get group statistics"""
        total_groups = len(self.groups)
        active_groups = len([g for g in self.groups if g.is_active])
        total_daily_invites = sum(g.current_daily_invites for g in self.groups)
        
        return {
            "total_groups": total_groups,
            "active_groups": active_groups,
            "total_daily_invites": total_daily_invites,
            "groups_details": [
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                    "is_active": group.is_active,
                    "daily_invites": group.current_daily_invites,
                    "max_daily_invites": group.max_daily_invites,
                    "assigned_accounts": group.assigned_accounts,
                    "invite_link": group.invite_link
                }
                for group in self.groups
            ]
        }
    
    def update_group(self, group_id: int, **kwargs) -> bool:
        """Update group parameters"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(group, key):
                setattr(group, key, value)
        
        # Save changes
        self.config_manager.save_groups(self.groups)
        logger.info(f"Group {group.group_name} updated")
        return True
    
    def add_group(self, group_id: int, group_name: str, invite_link: str, 
                  max_daily_invites: int = 100) -> bool:
        """Add new group"""
        try:
            new_group = self.config_manager.add_group(group_id, group_name, invite_link)
            new_group.max_daily_invites = max_daily_invites
            
            # Reload group list
            self.groups = self.config_manager.load_groups()
            logger.info(f"Added new group: {group_name}")
            return True
            
        except ValueError as e:
            logger.error(f"Error adding group: {e}")
            return False
    
    def remove_group(self, group_id: int) -> bool:
        """Remove group"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        self.groups.remove(group)
        self.config_manager.save_groups(self.groups)
        
        # Also remove invitation records for this group
        for user_invites in self.user_invitations.values():
            if group_id in user_invites:
                del user_invites[group_id]
        
        logger.info(f"Group {group.group_name} removed")
        return True
    
    def get_user_invitation_history(self, user_id: int) -> Dict[int, float]:
        """Get user invitation history"""
        return self.user_invitations.get(user_id, {})
    
    def validate_group_settings(self) -> List[str]:
        """Validate group settings"""
        issues = []
        
        for group in self.groups:
            # Check invite link presence
            if not group.invite_link or not group.invite_link.startswith('https://t.me/'):
                issues.append(f"Group {group.group_name}: invalid invite link")
            
            # Check assigned accounts
            if group.is_active and not group.assigned_accounts:
                issues.append(f"Group {group.group_name}: no assigned accounts")
            
            # Check limits
            if group.max_daily_invites <= 0:
                issues.append(f"Group {group.group_name}: invalid invitation limit")
        
        return issues