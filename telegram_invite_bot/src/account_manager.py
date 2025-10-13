"""
Telegram user account manager
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
    """User account manager for invitations"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.clients: Dict[str, Client] = {}
        self.accounts: List[UserAccount] = []
        
        # Get absolute path to sessions directory
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.session_dir = os.path.join(script_dir, "data", "sessions")
        
    async def initialize(self):
        """Initialize account manager"""
        self.accounts = self.config_manager.load_accounts()
        logger.info(f"Loaded {len(self.accounts)} accounts")
        
        # Create clients for each account
        for account in self.accounts:
            if account.is_active:
                await self._create_client(account)
    
    async def _create_client(self, account: UserAccount) -> Optional[Client]:
        """Create Pyrogram client for account"""
        try:
            client = Client(
                name=account.session_name,
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone,
                workdir=self.session_dir
            )
            
            # Connect to account
            await client.start()
            
            # Check that account is active
            me = await client.get_me()
            logger.info(f"Account {account.session_name} connected: {me.first_name} (@{me.username})")
            
            self.clients[account.session_name] = client
            return client
            
        except AuthKeyUnregistered:
            logger.error(f"Account {account.session_name}: Invalid authorization key")
            account.is_active = False
        except UserDeactivated:
            logger.error(f"Account {account.session_name}: Account deactivated")
            account.is_active = False
        except SessionPasswordNeeded:
            logger.error(f"Account {account.session_name}: 2FA password required")
            account.is_active = False
        except Exception as e:
            logger.error(f"Account connection error {account.session_name}: {e}")
            account.is_active = False
        
        return None
    
    def get_available_account(self, group_id: int = None) -> Optional[UserAccount]:
        """Get available account for invitation"""
        available_accounts = []
        
        for account in self.accounts:
            if not account.is_active:
                continue
                
            # If group is specified, check if account is assigned to this group
            if group_id and account.groups_assigned:
                if group_id not in account.groups_assigned:
                    continue
            
            available_accounts.append(account)
        
        if not available_accounts:
            return None
        
        # Return first available account
        return available_accounts[0]
    
    def get_active_accounts(self) -> List[UserAccount]:
        """Get all active accounts"""
        return [account for account in self.accounts if account.is_active]
    
    async def send_invite(self, account: UserAccount, user_id: int, group_link: str) -> bool:
        """Send invitation to user"""
        client = self.clients.get(account.session_name)
        if not client:
            logger.error(f"Client for account {account.session_name} not found")
            return False
        
        try:
            # Send invitation
            message_text = f"🎉 Hello! I invite you to join our group: {group_link}"
            
            await client.send_message(user_id, message_text)
            
            # Save changes (if needed)
            self.config_manager.save_accounts(self.accounts)
            
            logger.info(f"Invitation sent to user {user_id} via account {account.session_name}")
            return True
            
        except FloodWait as e:
            logger.warning(f"FloodWait for account {account.session_name}: waiting {e.value} seconds")
            # Temporarily deactivate account
            account.is_active = False
            # Can add logic for reactivation after certain time
            await asyncio.sleep(e.value)
            account.is_active = True
            return False
            
        except Exception as e:
            logger.error(f"Error sending invitation via {account.session_name}: {e}")
            return False
    
    async def check_user_in_group(self, account: UserAccount, user_id: int, group_id: int) -> bool:
        """Check if user is in group"""
        client = self.clients.get(account.session_name)
        if not client:
            return False
        
        try:
            member = await client.get_chat_member(group_id, user_id)
            return member.status in ["member", "administrator", "creator"]
        except Exception as e:
            logger.debug(f"User {user_id} not found in group {group_id}: {e}")
            return False
    
    async def get_group_invite_link(self, account: UserAccount, group_id: int) -> Optional[str]:
        """Get invitation link for group"""
        client = self.clients.get(account.session_name)
        if not client:
            return None
        
        try:
            chat = await client.get_chat(group_id)
            if chat.invite_link:
                return chat.invite_link
            
            # If no link exists, try to create one
            invite_link = await client.create_chat_invite_link(group_id)
            return invite_link.invite_link
            
        except Exception as e:
            logger.error(f"Error getting link for group {group_id}: {e}")
            return None
    

    
    async def shutdown(self):
        """Shutdown manager"""
        for client in self.clients.values():
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
        
        self.clients.clear()
        logger.info("All clients disconnected")
    
    def get_account_stats(self) -> Dict:
        """Get account statistics"""
        total_accounts = len(self.accounts)
        active_accounts = len([acc for acc in self.accounts if acc.is_active])
        
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "accounts_details": [
                {
                    "session_name": acc.session_name,
                    "phone": acc.phone,
                    "is_active": acc.is_active
                }
                for acc in self.accounts
            ]
        }
    
    async def test_account_connection(self, session_name: str) -> bool:
        """Test account connection"""
        client = self.clients.get(session_name)
        if not client:
            return False
        
        try:
            me = await client.get_me()
            logger.info(f"Connection test {session_name}: OK ({me.first_name})")
            return True
        except Exception as e:
            logger.error(f"Connection test {session_name}: FAILED ({e})")
            return False
    
    def get_client(self, session_name: str) -> Optional[Client]:
        """Get Pyrogram client for specific account"""
        return self.clients.get(session_name)
    
    async def join_group_with_accounts(self, group_invite_link: str, group_name: str = "Unknown") -> Dict[str, List[str]]:
        """Join a group with all available accounts
        
        Args:
            group_invite_link: Telegram invite link (https://t.me/+hash or https://t.me/username)
            group_name: Group name for logging
            
        Returns:
            Dict with 'success' and 'failed' lists containing account session names
        """
        results = {
            "success": [],
            "failed": []
        }
        
        # Extract invite hash or username from link
        invite_hash = None
        username = None
        
        if "t.me/+" in group_invite_link:
            invite_hash = group_invite_link.split("t.me/+")[-1]
        elif "t.me/" in group_invite_link:
            username = group_invite_link.split("t.me/")[-1]
            if username.startswith("@"):
                username = username[1:]
        else:
            logger.error(f"Invalid invite link format: {group_invite_link}")
            return results
        
        for account in self.accounts:
            if not account.is_active:
                continue
                
            client = self.clients.get(account.session_name)
            if not client:
                logger.warning(f"Client not available for account {account.session_name}")
                results["failed"].append(account.session_name)
                continue
            
            try:
                if invite_hash:
                    # Join using invite hash
                    chat = await client.join_chat(f"https://t.me/+{invite_hash}")
                    logger.info(f"Account {account.session_name} successfully joined {group_name} via invite hash")
                elif username:
                    # Join using username
                    chat = await client.join_chat(username)
                    logger.info(f"Account {account.session_name} successfully joined {group_name} via username")
                else:
                    logger.error(f"No valid invite method for {account.session_name}")
                    results["failed"].append(account.session_name)
                    continue
                
                results["success"].append(account.session_name)
                
                # Add delay between joins to avoid rate limiting
                await asyncio.sleep(random.uniform(2, 5))
                
            except FloodWait as e:
                logger.warning(f"FloodWait for account {account.session_name}: {e.value} seconds")
                results["failed"].append(account.session_name)
                # Could implement retry logic here
                
            except Exception as e:
                error_msg = str(e).lower()
                if "already" in error_msg or "participant" in error_msg:
                    logger.info(f"Account {account.session_name} already in group {group_name}")
                    results["success"].append(account.session_name)
                else:
                    logger.error(f"Failed to join {group_name} with account {account.session_name}: {e}")
                    results["failed"].append(account.session_name)
        
        logger.info(f"Group join results for {group_name}: {len(results['success'])} success, {len(results['failed'])} failed")
        return results
    
    async def auto_join_all_groups(self, groups: List) -> Dict[str, Dict]:
        """Automatically join all accounts to all active groups
        
        Args:
            groups: List of TelegramGroup objects
            
        Returns:
            Dict with results for each group
        """
        all_results = {}
        
        for group in groups:
            if not group.is_active:
                continue
                
            logger.info(f"Starting auto-join for group: {group.group_name}")
            
            try:
                results = await self.join_group_with_accounts(
                    group.invite_link, 
                    group.group_name
                )
                all_results[group.group_name] = results
                
                # Delay between different groups
                await asyncio.sleep(random.uniform(5, 10))
                
            except Exception as e:
                logger.error(f"Error in auto-join for group {group.group_name}: {e}")
                all_results[group.group_name] = {
                    "success": [],
                    "failed": [acc.session_name for acc in self.accounts if acc.is_active]
                }
        
        return all_results