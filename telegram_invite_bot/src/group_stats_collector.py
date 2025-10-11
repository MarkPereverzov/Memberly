"""
Group statistics collector
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .database_manager import DatabaseManager
from .group_manager import GroupManager
from .account_manager import AccountManager

logger = logging.getLogger(__name__)

class GroupStatsCollector:
    """Collects and updates group statistics periodically"""
    
    def __init__(self, database_manager: DatabaseManager, 
                 group_manager: GroupManager, 
                 account_manager: AccountManager):
        self.db = database_manager
        self.group_manager = group_manager
        self.account_manager = account_manager
        
        # Collection settings
        self.collection_interval = 3600  # 1 hour in seconds
        self.max_retries = 3
        self.retry_delay = 60  # 1 minute
        
        # Task management
        self._collection_task = None
        self._running = False
    
    async def start_collection(self):
        """Start periodic group statistics collection"""
        if self._running:
            logger.warning("Group statistics collection already running")
            return
        
        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Started group statistics collection")
    
    async def stop_collection(self):
        """Stop periodic group statistics collection"""
        if not self._running:
            return
        
        self._running = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped group statistics collection")
    
    async def _collection_loop(self):
        """Main collection loop"""
        while self._running:
            try:
                await self.collect_all_group_stats()
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in group statistics collection loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def collect_all_group_stats(self) -> bool:
        """Collect statistics for all active groups"""
        try:
            active_groups = self.group_manager.get_active_groups()
            
            if not active_groups:
                logger.info("No active groups to collect statistics for")
                return True
            
            logger.info(f"Collecting statistics for {len(active_groups)} groups")
            
            successful_collections = 0
            total_groups = len(active_groups)
            
            for group in active_groups:
                try:
                    success = await self.collect_group_stats(group.group_id, group.group_name)
                    if success:
                        successful_collections += 1
                    
                    # Small delay between requests to avoid rate limiting
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error collecting stats for group {group.group_name}: {e}")
            
            success_rate = (successful_collections / total_groups) * 100
            logger.info(f"Collection completed: {successful_collections}/{total_groups} groups ({success_rate:.1f}%)")
            
            return success_rate > 50  # Consider successful if > 50% of groups were processed
            
        except Exception as e:
            logger.error(f"Error in collect_all_group_stats: {e}")
            return False
    
    async def collect_group_stats(self, group_id: int, group_name: str) -> bool:
        """Collect statistics for a specific group"""
        for attempt in range(self.max_retries):
            try:
                # Get available account for the group
                account = self.account_manager.get_available_account(group_id)
                if not account:
                    logger.warning(f"No available account for group {group_name}")
                    return False
                
                # Try to get group information
                member_count = await self._get_group_member_count(account, group_id)
                
                if member_count is not None:
                    # Update database with new statistics
                    success = self.db.update_group_stats(group_id, group_name, member_count)
                    
                    if success:
                        logger.debug(f"Updated stats for {group_name}: {member_count} members")
                        return True
                    else:
                        logger.error(f"Failed to save stats for {group_name}")
                        return False
                else:
                    logger.warning(f"Could not get member count for {group_name} (attempt {attempt + 1})")
                    
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                
            except Exception as e:
                logger.error(f"Error collecting stats for {group_name} (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"Failed to collect stats for {group_name} after {self.max_retries} attempts")
        return False
    
    async def _get_group_member_count(self, account, group_id: int) -> Optional[int]:
        """Get member count for a group using Pyrogram client"""
        try:
            client = account.client
            if not client:
                logger.error("Client not available")
                return None
            
            # Get chat information
            chat = await client.get_chat(group_id)
            
            if chat and hasattr(chat, 'members_count'):
                return chat.members_count
            else:
                logger.warning(f"Could not get member count for group {group_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting group member count: {e}")
            return None
    
    async def force_collection(self) -> Dict[str, int]:
        """Force immediate collection of all group statistics"""
        logger.info("Force collecting group statistics")
        
        active_groups = self.group_manager.get_active_groups()
        results = {
            "total_groups": len(active_groups),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for group in active_groups:
            try:
                success = await self.collect_group_stats(group.group_id, group.group_name)
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to collect stats for {group.group_name}")
                
                # Small delay between requests
                await asyncio.sleep(1)
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error with {group.group_name}: {str(e)}")
        
        logger.info(f"Force collection completed: {results['successful']}/{results['total_groups']} successful")
        return results
    
    def get_collection_status(self) -> Dict:
        """Get current collection status"""
        return {
            "running": self._running,
            "interval_seconds": self.collection_interval,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay
        }
    
    def update_collection_settings(self, interval_seconds: Optional[int] = None,
                                 max_retries: Optional[int] = None,
                                 retry_delay_seconds: Optional[int] = None):
        """Update collection settings"""
        if interval_seconds is not None:
            self.collection_interval = max(300, interval_seconds)  # Minimum 5 minutes
        
        if max_retries is not None:
            self.max_retries = max(1, max_retries)
        
        if retry_delay_seconds is not None:
            self.retry_delay = max(10, retry_delay_seconds)  # Minimum 10 seconds
        
        logger.info(f"Updated collection settings: interval={self.collection_interval}s, "
                   f"retries={self.max_retries}, delay={self.retry_delay}s")
    
    async def get_group_stats_history(self, group_id: int, days: int = 30) -> List[Dict]:
        """Get historical statistics for a group (placeholder for future implementation)"""
        # This would require storing historical data in the database
        # For now, return current stats
        current_stats = self.db.get_group_stats(group_id)
        
        if current_stats:
            return [{
                "date": datetime.fromtimestamp(current_stats.last_updated).isoformat(),
                "member_count": current_stats.member_count
            }]
        
        return []
    
    async def cleanup_old_stats(self, days: int = 90) -> int:
        """Clean up old statistics (placeholder for future implementation)"""
        # This would clean up historical statistics data
        # For now, we only keep current stats, so nothing to clean
        logger.info(f"Stats cleanup requested for data older than {days} days")
        return 0