"""
Система кулдаунов и защиты от бана
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
    """Запись о кулдауне"""
    user_id: int
    last_invite_time: float
    invite_count_today: int
    last_reset_date: str
    blocked_until: Optional[float] = None

class CooldownManager:
    """Менеджер кулдаунов и защиты от спама"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.cooldowns_file = os.path.join(data_dir, "cooldowns.json")
        self.user_cooldowns: Dict[int, CooldownRecord] = {}
        self.group_last_invite: Dict[int, float] = {}  # group_id -> timestamp
        
        # Настройки кулдаунов
        self.invite_cooldown_seconds = 300  # 5 минут между приглашениями
        self.group_cooldown_seconds = 60    # 1 минута между приглашениями в группы
        self.max_invites_per_day = 10       # Максимум приглашений в день
        self.ban_duration_hours = 24        # Длительность бана в часах
        
        self.load_cooldowns()
    
    def load_cooldowns(self):
        """Загрузка данных о кулдаунах"""
        if not os.path.exists(self.cooldowns_file):
            return
        
        try:
            with open(self.cooldowns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for user_id_str, record_data in data.items():
                user_id = int(user_id_str)
                self.user_cooldowns[user_id] = CooldownRecord(**record_data)
                
            logger.info(f"Загружено {len(self.user_cooldowns)} записей кулдаунов")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки кулдаунов: {e}")
    
    def save_cooldowns(self):
        """Сохранение данных о кулдаунах"""
        try:
            data = {}
            for user_id, record in self.user_cooldowns.items():
                data[str(user_id)] = {
                    'user_id': record.user_id,
                    'last_invite_time': record.last_invite_time,
                    'invite_count_today': record.invite_count_today,
                    'last_reset_date': record.last_reset_date,
                    'blocked_until': record.blocked_until
                }
            
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.cooldowns_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения кулдаунов: {e}")
    
    def can_user_request_invite(self, user_id: int) -> tuple[bool, str]:
        """Проверка, может ли пользователь запросить приглашение"""
        current_time = time.time()
        today = time.strftime("%Y-%m-%d")
        
        # Получаем или создаем запись для пользователя
        if user_id not in self.user_cooldowns:
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=0,
                invite_count_today=0,
                last_reset_date=today
            )
        
        record = self.user_cooldowns[user_id]
        
        # Проверяем блокировку
        if record.blocked_until and current_time < record.blocked_until:
            remaining_time = int(record.blocked_until - current_time)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            return False, f"Вы заблокированы до {time.strftime('%H:%M %d.%m.%Y', time.localtime(record.blocked_until))} (осталось {hours}ч {minutes}м)"
        
        # Сбрасываем дневной счетчик если новый день
        if record.last_reset_date != today:
            record.invite_count_today = 0
            record.last_reset_date = today
            record.blocked_until = None
        
        # Проверяем дневной лимит
        if record.invite_count_today >= self.max_invites_per_day:
            return False, f"Вы достигли дневного лимита приглашений ({self.max_invites_per_day}). Попробуйте завтра."
        
        # Проверяем кулдаун между приглашениями
        time_since_last = current_time - record.last_invite_time
        if time_since_last < self.invite_cooldown_seconds:
            remaining_cooldown = int(self.invite_cooldown_seconds - time_since_last)
            minutes = remaining_cooldown // 60
            seconds = remaining_cooldown % 60
            return False, f"Подождите {minutes}м {seconds}с перед следующим приглашением."
        
        return True, "OK"
    
    def can_invite_to_group(self, group_id: int) -> tuple[bool, str]:
        """Проверка, можно ли отправить приглашение в группу"""
        current_time = time.time()
        
        if group_id in self.group_last_invite:
            time_since_last = current_time - self.group_last_invite[group_id]
            if time_since_last < self.group_cooldown_seconds:
                remaining_cooldown = int(self.group_cooldown_seconds - time_since_last)
                return False, f"Кулдаун группы: подождите {remaining_cooldown}с"
        
        return True, "OK"
    
    def record_invite_attempt(self, user_id: int, group_id: int, success: bool):
        """Запись попытки приглашения"""
        current_time = time.time()
        
        # Обновляем запись пользователя
        if user_id in self.user_cooldowns:
            record = self.user_cooldowns[user_id]
            record.last_invite_time = current_time
            
            if success:
                record.invite_count_today += 1
                
                # Проверяем, не достиг ли пользователь лимита
                if record.invite_count_today >= self.max_invites_per_day:
                    logger.warning(f"Пользователь {user_id} достиг дневного лимита приглашений")
        
        # Обновляем время последнего приглашения в группу
        if success:
            self.group_last_invite[group_id] = current_time
        
        self.save_cooldowns()
    
    def block_user(self, user_id: int, duration_hours: Optional[int] = None):
        """Блокировка пользователя"""
        if duration_hours is None:
            duration_hours = self.ban_duration_hours
        
        current_time = time.time()
        block_until = current_time + (duration_hours * 3600)
        
        if user_id not in self.user_cooldowns:
            today = time.strftime("%Y-%m-%d")
            self.user_cooldowns[user_id] = CooldownRecord(
                user_id=user_id,
                last_invite_time=current_time,
                invite_count_today=0,
                last_reset_date=today
            )
        
        self.user_cooldowns[user_id].blocked_until = block_until
        self.save_cooldowns()
        
        logger.warning(f"Пользователь {user_id} заблокирован на {duration_hours} часов")
    
    def unblock_user(self, user_id: int):
        """Разблокировка пользователя"""
        if user_id in self.user_cooldowns:
            self.user_cooldowns[user_id].blocked_until = None
            self.save_cooldowns()
            logger.info(f"Пользователь {user_id} разблокирован")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        if user_id not in self.user_cooldowns:
            return {
                "invite_count_today": 0,
                "last_invite_time": 0,
                "is_blocked": False,
                "blocked_until": None,
                "can_invite": True
            }
        
        record = self.user_cooldowns[user_id]
        current_time = time.time()
        
        is_blocked = record.blocked_until and current_time < record.blocked_until
        can_invite, _ = self.can_user_request_invite(user_id)
        
        return {
            "invite_count_today": record.invite_count_today,
            "last_invite_time": record.last_invite_time,
            "is_blocked": is_blocked,
            "blocked_until": record.blocked_until,
            "can_invite": can_invite,
            "remaining_invites": max(0, self.max_invites_per_day - record.invite_count_today)
        }
    
    def reset_daily_stats(self):
        """Сброс дневной статистики"""
        today = time.strftime("%Y-%m-%d")
        
        for record in self.user_cooldowns.values():
            record.invite_count_today = 0
            record.last_reset_date = today
            # Не сбрасываем блокировки - они должны истечь сами
        
        self.save_cooldowns()
        logger.info("Дневная статистика кулдаунов сброшена")
    
    def cleanup_expired_blocks(self):
        """Очистка истекших блокировок"""
        current_time = time.time()
        cleaned_count = 0
        
        for record in self.user_cooldowns.values():
            if record.blocked_until and current_time >= record.blocked_until:
                record.blocked_until = None
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.save_cooldowns()
            logger.info(f"Очищено {cleaned_count} истекших блокировок")
    
    def get_global_stats(self) -> Dict:
        """Получение глобальной статистики"""
        current_time = time.time()
        
        total_users = len(self.user_cooldowns)
        active_blocks = sum(1 for r in self.user_cooldowns.values() 
                           if r.blocked_until and current_time < r.blocked_until)
        total_invites_today = sum(r.invite_count_today for r in self.user_cooldowns.values())
        
        return {
            "total_users": total_users,
            "active_blocks": active_blocks,
            "total_invites_today": total_invites_today,
            "max_invites_per_day": self.max_invites_per_day,
            "invite_cooldown_seconds": self.invite_cooldown_seconds,
            "group_cooldown_seconds": self.group_cooldown_seconds
        }
    
    def update_settings(self, invite_cooldown: Optional[int] = None, 
                       group_cooldown: Optional[int] = None,
                       max_invites: Optional[int] = None):
        """Обновление настроек кулдаунов"""
        if invite_cooldown is not None:
            self.invite_cooldown_seconds = invite_cooldown
        
        if group_cooldown is not None:
            self.group_cooldown_seconds = group_cooldown
        
        if max_invites is not None:
            self.max_invites_per_day = max_invites
        
        logger.info("Настройки кулдаунов обновлены")
    
    def get_recent_activity(self, hours: int = 24) -> List[Dict]:
        """Получение недавней активности"""
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        recent_activity = []
        for record in self.user_cooldowns.values():
            if record.last_invite_time >= cutoff_time:
                recent_activity.append({
                    "user_id": record.user_id,
                    "last_invite_time": record.last_invite_time,
                    "invite_count_today": record.invite_count_today,
                    "is_blocked": record.blocked_until and current_time < record.blocked_until
                })
        
        # Сортируем по времени последнего приглашения
        recent_activity.sort(key=lambda x: x["last_invite_time"], reverse=True)
        
        return recent_activity