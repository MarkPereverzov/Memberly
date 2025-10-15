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
            
            # Connect to account with retry logic for database locks
            max_retries = 3
            for retry in range(max_retries):
                try:
                    await client.start()
                    break
                except Exception as e:
                    if "database is locked" in str(e).lower() and retry < max_retries - 1:
                        logger.warning(f"Database locked for {account.session_name}, retrying in {retry + 1} seconds...")
                        await asyncio.sleep(retry + 1)
                        continue
                    else:
                        raise e
            
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

    async def add_user_to_contacts(self, account: UserAccount, user_id: int) -> tuple[bool, str]:
        """Try to establish contact with user"""
        client = self.clients.get(account.session_name)
        if not client:
            logger.error(f"Client for account {account.session_name} not found")
            return False, "Client not available"
        
        try:
            # Try to resolve the peer first
            try:
                peer = await client.resolve_peer(user_id)
                logger.debug(f"Successfully resolved peer for user {user_id}")
            except Exception as resolve_error:
                error_str = str(resolve_error).lower()
                if "peer_id_invalid" in error_str:
                    logger.warning(f"Cannot resolve peer {user_id}: User not accessible")
                    return False, "User not accessible - they may need to message bot first"
                else:
                    logger.warning(f"Peer resolve error for {user_id}: {resolve_error}")
                    return False, f"Cannot resolve user: {str(resolve_error)}"
            
            # Get user info
            user_info = await client.get_users(user_id)
            
            # Check if already in contacts
            if hasattr(user_info, 'is_contact') and user_info.is_contact:
                logger.info(f"User {user_id} already in contacts of {account.session_name}")
                return True, "Already in contacts"
            
            # Get username for better error messages
            username = getattr(user_info, 'username', None)
            first_name = getattr(user_info, 'first_name', 'User')
            
            # Try to add to contacts using phone number or username
            try:
                # If user has username, try adding by username
                if username:
                    contact_result = await client.add_contact(user_id, first_name, "")
                    if contact_result:
                        logger.info(f"Successfully added user {user_id} (@{username}) to contacts")
                        return True, "Added to contacts"
                else:
                    # For users without username, we can't add them directly
                    logger.info(f"User {user_id} has no username, cannot add to contacts directly")
                    return False, "User has no username - they must message bot first"
                    
            except Exception as add_error:
                error_str = str(add_error).lower()
                logger.warning(f"Failed to add user {user_id} to contacts: {add_error}")
                return False, f"Cannot add to contacts: User must message bot first"
            
        except Exception as e:
            error_str = str(e).lower()
            if "peer_id_invalid" in error_str:
                logger.warning(f"Could not find user {user_id} with {account.session_name}: User ID is invalid or user is not accessible")
                return False, "User not found or not accessible (check privacy settings)"
            else:
                logger.warning(f"Could not check contact status for user {user_id} with {account.session_name}: {e}")
                return False, f"Contact check failed: {str(e)}"

    async def send_contact_message(self, account: UserAccount, user_id: int, bot_username: str = None) -> tuple[bool, str]:
        """Send a message to establish contact with user through bot account"""
        client = self.clients.get(account.session_name)
        if not client:
            logger.error(f"Client for account {account.session_name} not found")
            return False, "Client not available"
        
        try:
            # First check if we can resolve the user
            try:
                peer = await client.resolve_peer(user_id)
            except Exception as resolve_error:
                if "peer_id_invalid" in str(resolve_error).lower():
                    return False, "User must start conversation with bot first"
                else:
                    return False, f"Cannot reach user: {str(resolve_error)}"
            
            # Try to send a contact establishment message
            try:
                message_text = f"""
🤖 **Hello from our Invitation System!**

To ensure smooth group invitations, please:
1. Reply to this message with any text (like "hi")
2. Then use /invite command again

This helps establish contact for better invitation success rates.
                """
                
                await client.send_message(user_id, message_text)
                logger.info(f"Contact message sent to user {user_id} from {account.session_name}")
                return True, "Contact message sent - user should reply to establish contact"
                
            except Exception as send_error:
                error_str = str(send_error).lower()
                if "user_is_blocked" in error_str:
                    return False, "User has blocked our account"
                elif "peer_id_invalid" in error_str:
                    return False, "User must start conversation with bot first"
                elif "chat_write_forbidden" in error_str:
                    return False, "Cannot message user - privacy settings prevent contact"
                else:
                    logger.warning(f"Failed to send contact message to {user_id}: {send_error}")
                    return False, f"Cannot send message: {str(send_error)}"
                    
        except Exception as e:
            logger.error(f"Error in send_contact_message for user {user_id}: {e}")
            return False, f"Contact message failed: {str(e)}"

    async def get_bot_info(self, account: UserAccount) -> tuple[bool, str]:
        """Get information about the bot account for user instructions"""
        client = self.clients.get(account.session_name)
        if not client:
            return False, "Client not available"
        
        try:
            me = await client.get_me()
            username = getattr(me, 'username', None)
            first_name = getattr(me, 'first_name', 'Bot')
            
            if username:
                return True, f"@{username}"
            else:
                return True, f"{first_name} ({me.phone or 'Bot Account'})"
                
        except Exception as e:
            logger.error(f"Could not get bot info: {e}")
            return False, "Unknown Bot Account"

    async def add_user_to_group(self, account: UserAccount, user_id: int, group_id: int, invite_link: str = None) -> tuple[bool, str]:
        """Add user directly to group - with contact checking"""
        client = self.clients.get(account.session_name)
        if not client:
            logger.error(f"Client for account {account.session_name} not found")
            return False, "Client not available"
        
        try:
            # Simple approach: use group_id directly
            group_title = f"Group {abs(group_id)}"  # Simple fallback name
            
            # Step 1: Check contact status (don't try to add, just check)
            logger.info(f"Checking contact status for user {user_id} with {account.session_name}")
            contact_success, contact_message = await self.add_user_to_contacts(account, user_id)
            
            if contact_success:
                logger.info(f"Contact status: {contact_message}")
            else:
                logger.warning(f"Contact issue: {contact_message}")
            
            # Step 2: Check if user is already in the group
            try:
                member = await client.get_chat_member(group_id, user_id)
                if member.status in ["member", "administrator", "creator"]:
                    logger.info(f"User {user_id} already in group {group_title}")
                    return True, "User already in group"
            except Exception as membership_check_error:
                logger.debug(f"Could not check membership for user {user_id} in group {group_id}: {membership_check_error}")
                # Continue with adding - user might not be in group
            
            # Step 3: Try to add user directly to group
            try:
                # Direct add attempt
                await client.add_chat_members(group_id, user_id)
                logger.info(f"User {user_id} successfully added to group {group_id} via account {account.session_name}")
                return True, f"Successfully added to group"
                
            except Exception as direct_add_error:
                error_str = str(direct_add_error).lower()
                
                if "user_already_participant" in error_str:
                    logger.info(f"User {user_id} already in group {group_id}")
                    return True, "User already in group"
                elif "peer_id_invalid" in error_str:
                    if contact_success:
                        logger.warning(f"PEER_ID_INVALID: Cannot add user {user_id} to group {group_id} despite having contact")
                        return False, "Cannot add: User may have privacy restrictions"
                    else:
                        logger.warning(f"PEER_ID_INVALID: Cannot add user {user_id} to group {group_id} - no contact established")
                        
                        # Try to send invite link instead
                        if invite_link:
                            try:
                                # Get user info for better messaging
                                user_info = await client.get_users(user_id)
                                username = getattr(user_info, 'username', None)
                                
                                # We can't send DM, but we can provide the invite link in response
                                return False, f"Cannot add directly. Please share invite link: {invite_link}"
                            except:
                                return False, f"Cannot add: User must start conversation with bot first. Invite link: {invite_link or 'N/A'}"
                        else:
                            return False, "Cannot add: User must message our bot account first"
                else:
                    logger.error(f"Failed to add user {user_id} to group {group_id}: {direct_add_error}")
                    return False, f"Failed to add: {str(direct_add_error)}"
            
        except FloodWait as e:
            logger.warning(f"FloodWait for account {account.session_name}: waiting {e.value} seconds")
            # Temporarily deactivate account
            account.is_active = False
            await asyncio.sleep(e.value)
            account.is_active = True
            return False, f"Rate limited, waiting {e.value} seconds"
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle specific error cases
            if "user_privacy_restricted" in error_msg:
                return False, "User privacy settings don't allow adding to groups"
            elif "user_not_mutual_contact" in error_msg:
                return False, "User must be a mutual contact to be added"
            elif "user_already_participant" in error_msg:
                return True, "User already in group"
            elif "chat_admin_required" in error_msg:
                return False, "Admin rights required to add users"
            elif "too_many_requests" in error_msg:
                return False, "Too many requests, try again later"
            elif "peer id invalid" in error_msg:
                # More specific handling for peer ID invalid
                if "user" in error_msg.lower():
                    return False, f"User {user_id} not found or has privacy restrictions"
                else:
                    return False, f"Invalid group ID: {group_id}"
            elif "chatpreview" in error_msg and "attribute" in error_msg:
                return False, "Chat preview error - group may be private"
            elif "has no attribute 'id'" in error_msg:
                return False, "Chat object error - unable to access group"
            else:
                logger.error(f"Error adding user {user_id} to group {group_id} via {account.session_name}: {e}")
                return False, f"Error: {str(e)}"
    
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
    
    async def get_group_member_count(self, group_id: int, invite_link: str = None) -> Optional[int]:
        """Get member count for group using any available account"""
        active_accounts = [acc for acc in self.accounts if acc.is_active]
        available_clients = [(acc, self.clients.get(acc.session_name)) for acc in active_accounts if self.clients.get(acc.session_name)]
        
        if not available_clients:
            logger.error(f"No available clients to get member count for group {group_id}")
            return None
            
        logger.info(f"Attempting to get member count for group {group_id} using {len(available_clients)} available clients")
        
        for account, client in available_clients:
            try:
                logger.debug(f"Trying to get group info via {account.session_name}")
                
                # Try to get chat by invite link first if available
                chat = None
                if invite_link:
                    try:
                        # Extract chat identifier from invite link
                        if "t.me/+" in invite_link:
                            # Private group invite link - try to join first
                            logger.debug(f"Using private invite link: {invite_link}")
                            try:
                                chat = await client.get_chat(invite_link)
                            except Exception as link_error:
                                logger.warning(f"Could not access group via invite link {invite_link}: {link_error}")
                                # Try to join via invite link
                                try:
                                    chat = await client.join_chat(invite_link)
                                    logger.info(f"Joined group via invite link: {invite_link}")
                                except Exception as join_error:
                                    logger.warning(f"Could not join group via invite link {invite_link}: {join_error}")
                        else:
                            # Public group - try username
                            username = invite_link.split('/')[-1]
                            chat = await client.get_chat(username)
                    except Exception as e:
                        logger.debug(f"Could not get chat via invite link: {e}")
                
                # If invite link didn't work, try direct ID
                if not chat:
                    try:
                        chat = await client.get_chat(group_id)
                    except Exception as id_error:
                        logger.debug(f"Could not get chat via ID {group_id}: {id_error}")
                        continue
                
                # Check if we got valid chat info
                if chat and hasattr(chat, 'members_count') and chat.members_count is not None:
                    logger.info(f"Group {group_id} has {chat.members_count} members (via {account.session_name})")
                    return chat.members_count
                elif chat:
                    logger.warning(f"Chat {group_id}: members_count not available. Chat type: {getattr(chat, 'type', 'unknown')}")
                    
                    # Try to check if we're a member of this chat
                    try:
                        me = await client.get_me()
                        member = await client.get_chat_member(chat.id, me.id)
                        logger.info(f"Account {account.session_name} status in group {chat.id}: {member.status}")
                        
                        # If we're not a member, we can't get member count
                        if member.status not in ["member", "administrator", "creator"]:
                            logger.warning(f"Account {account.session_name} is not a member of group {chat.id}")
                        
                    except Exception as member_error:
                        logger.warning(f"Could not check membership status for group {group_id}: {member_error}")
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "chat not found" in error_msg:
                    logger.error(f"Group {group_id} not found or not accessible via {account.session_name}")
                elif "forbidden" in error_msg:
                    logger.error(f"Access forbidden to group {group_id} via {account.session_name}")
                elif "peer id invalid" in error_msg:
                    logger.error(f"Invalid peer ID {group_id} - group may not be accessible via {account.session_name}")
                else:
                    logger.debug(f"Failed to get member count for group {group_id} via {account.session_name}: {e}")
                continue
        
        logger.warning(f"Could not get member count for group {group_id} with any account")
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
    
    async def get_detailed_account_stats(self) -> Dict:
        """Get detailed account statistics with user IDs and connection status"""
        detailed_accounts = []
        
        for acc in self.accounts:
            account_info = {
                "session_name": acc.session_name,
                "phone": acc.phone,
                "is_active": acc.is_active,
                "is_connected": False,
                "user_id": "Unknown",
                "username": "Unknown",
                "first_name": "Unknown"
            }
            
            # Try to get detailed info if client exists and account is active
            if acc.is_active:
                client = self.clients.get(acc.session_name)
                if client:
                    try:
                        me = await client.get_me()
                        account_info.update({
                            "is_connected": True,
                            "user_id": me.id,
                            "username": me.username or "No username",
                            "first_name": me.first_name or "Unknown"
                        })
                        logger.debug(f"Got detailed info for {acc.session_name}: {me.id}")
                    except Exception as e:
                        logger.warning(f"Failed to get detailed info for {acc.session_name}: {e}")
                        account_info["is_connected"] = False
            
            detailed_accounts.append(account_info)
        
        total_accounts = len(self.accounts)
        active_accounts = len([acc for acc in detailed_accounts if acc.get('is_active', False)])
        connected_accounts = len([acc for acc in detailed_accounts if acc.get('is_connected', False)])
        
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "connected_accounts": connected_accounts,
            "accounts_details": detailed_accounts
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
        
        # Check if we have any active accounts
        active_accounts = [acc for acc in self.accounts if acc.is_active]
        if not active_accounts:
            logger.error("No active accounts available for group joining")
            return results
        
        logger.info(f"Attempting to join group {group_name} with {len(active_accounts)} active accounts")
        
        # Extract invite hash or username from link
        invite_hash = None
        username = None
        
        if "t.me/+" in group_invite_link:
            invite_hash = group_invite_link.split("t.me/+")[-1]
            logger.debug(f"Using invite hash: {invite_hash[:10]}...")
        elif "t.me/" in group_invite_link:
            username = group_invite_link.split("t.me/")[-1]
            if username.startswith("@"):
                username = username[1:]
            logger.debug(f"Using username: {username}")
        else:
            logger.error(f"Invalid invite link format: {group_invite_link}")
            return results
        
        for account in active_accounts:
            client = self.clients.get(account.session_name)
            if not client:
                logger.warning(f"Client not available for account {account.session_name}")
                results["failed"].append(account.session_name)
                continue
            
            logger.info(f"Attempting to join {group_name} with account {account.session_name}")
            
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
    
    async def join_group_and_get_id(self, invite_link: str, group_name: str) -> tuple[bool, int, str]:
        """Join group by invite link and get its ID automatically
        
        Args:
            invite_link: Telegram invite link (https://t.me/+hash or https://t.me/username)
            group_name: Group name for logging
            
        Returns:
            Tuple of (success: bool, group_id: int, message: str)
        """
        # Get first available account
        active_accounts = [acc for acc in self.accounts if acc.is_active]
        if not active_accounts:
            return False, 0, "No active accounts available"
        
        account = active_accounts[0]  # Use first available account
        client = self.clients.get(account.session_name)
        if not client:
            return False, 0, f"Client not available for account {account.session_name}"
        
        try:
            logger.info(f"Attempting to join group '{group_name}' to get ID...")
            
            # Join the group and get chat info
            chat = await client.join_chat(invite_link)
            
            # Get group ID from chat object
            group_id = chat.id
            chat_title = getattr(chat, 'title', group_name)
            
            logger.info(f"Successfully joined group '{chat_title}' with ID: {group_id}")
            
            return True, group_id, f"Successfully joined and retrieved ID: {group_id}"
            
        except Exception as e:
            error_msg = str(e).lower()
            if "already" in error_msg or "participant" in error_msg:
                # Already a member - try to get chat info
                try:
                    # Extract identifier from invite link
                    if "t.me/+" in invite_link:
                        chat = await client.get_chat(invite_link)
                    elif "t.me/" in invite_link:
                        username = invite_link.split("t.me/")[-1]
                        if username.startswith("@"):
                            username = username[1:]
                        chat = await client.get_chat(username)
                    else:
                        return False, 0, f"Invalid invite link format: {invite_link}"
                    
                    group_id = chat.id
                    chat_title = getattr(chat, 'title', group_name)
                    logger.info(f"Already member of group '{chat_title}' with ID: {group_id}")
                    
                    return True, group_id, f"Already member, retrieved ID: {group_id}"
                    
                except Exception as get_error:
                    logger.error(f"Could not get group info after join attempt: {get_error}")
                    return False, 0, f"Already member but could not retrieve ID: {get_error}"
            else:
                logger.error(f"Failed to join group '{group_name}': {e}")
                return False, 0, f"Failed to join group: {e}"