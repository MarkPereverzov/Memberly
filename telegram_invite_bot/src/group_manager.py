"""
Менеджер групп для бота-приглашающего
"""
import logging
import time
from typing import List, Optional, Dict, Set
from config.config import TelegramGroup, ConfigManager

logger = logging.getLogger(__name__)

class GroupManager:
    """Менеджер целевых групп для приглашений"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.groups: List[TelegramGroup] = []
        self.user_invitations: Dict[int, Dict[int, float]] = {}  # user_id -> {group_id: timestamp}
        
    def initialize(self):
        """Инициализация менеджера групп"""
        self.groups = self.config_manager.load_groups()
        logger.info(f"Загружено {len(self.groups)} групп")
    
    def get_available_groups_for_user(self, user_id: int) -> List[TelegramGroup]:
        """Получение списка групп, в которые пользователь еще не был приглашен"""
        available_groups = []
        user_invites = self.user_invitations.get(user_id, {})
        
        for group in self.groups:
            if not group.is_active:
                continue
                
            # Проверяем, не достигнут ли дневной лимит приглашений для группы
            if group.current_daily_invites >= group.max_daily_invites:
                continue
                
            # Проверяем, не был ли пользователь уже приглашен в эту группу
            if group.group_id in user_invites:
                # Проверяем кулдаун (например, 24 часа)
                last_invite_time = user_invites[group.group_id]
                if time.time() - last_invite_time < 24 * 60 * 60:  # 24 часа
                    continue
            
            available_groups.append(group)
        
        return available_groups
    
    def get_group_by_id(self, group_id: int) -> Optional[TelegramGroup]:
        """Получение группы по ID"""
        for group in self.groups:
            if group.group_id == group_id:
                return group
        return None
    
    def get_active_groups(self) -> List[TelegramGroup]:
        """Получение всех активных групп"""
        return [group for group in self.groups if group.is_active]
    
    def select_best_group_for_user(self, user_id: int) -> Optional[TelegramGroup]:
        """Выбор лучшей группы для приглашения пользователя"""
        available_groups = self.get_available_groups_for_user(user_id)
        
        if not available_groups:
            return None
        
        # Сортируем группы по количеству приглашений (меньше приглашений = выше приоритет)
        available_groups.sort(key=lambda x: x.current_daily_invites)
        
        return available_groups[0]
    
    def record_invitation(self, user_id: int, group_id: int) -> bool:
        """Запись приглашения пользователя в группу"""
        group = self.get_group_by_id(group_id)
        if not group:
            logger.error(f"Группа с ID {group_id} не найдена")
            return False
        
        # Записываем приглашение
        if user_id not in self.user_invitations:
            self.user_invitations[user_id] = {}
        
        self.user_invitations[user_id][group_id] = time.time()
        
        # Увеличиваем счетчик приглашений для группы
        group.current_daily_invites += 1
        
        # Сохраняем изменения
        self.config_manager.save_groups(self.groups)
        
        logger.info(f"Записано приглашение пользователя {user_id} в группу {group.group_name}")
        return True
    
    def check_group_cooldown(self, group_id: int, cooldown_seconds: int = 60) -> bool:
        """Проверка кулдауна группы"""
        # Это можно расширить для отслеживания последнего приглашения в каждую группу
        # Пока что возвращаем True (кулдаун прошел)
        return True
    
    def get_groups_by_account(self, session_name: str) -> List[TelegramGroup]:
        """Получение групп, назначенных на конкретный аккаунт"""
        assigned_groups = []
        for group in self.groups:
            if session_name in group.assigned_accounts:
                assigned_groups.append(group)
        return assigned_groups
    
    def assign_account_to_group(self, session_name: str, group_id: int) -> bool:
        """Назначение аккаунта на группу"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        if session_name not in group.assigned_accounts:
            group.assigned_accounts.append(session_name)
            self.config_manager.save_groups(self.groups)
            logger.info(f"Аккаунт {session_name} назначен на группу {group.group_name}")
        
        return True
    
    def remove_account_from_group(self, session_name: str, group_id: int) -> bool:
        """Удаление аккаунта из группы"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        if session_name in group.assigned_accounts:
            group.assigned_accounts.remove(session_name)
            self.config_manager.save_groups(self.groups)
            logger.info(f"Аккаунт {session_name} удален из группы {group.group_name}")
        
        return True
    
    def reset_daily_stats(self):
        """Сброс дневной статистики групп"""
        for group in self.groups:
            group.current_daily_invites = 0
        
        self.config_manager.save_groups(self.groups)
        logger.info("Дневная статистика групп сброшена")
    
    def get_group_stats(self) -> Dict:
        """Получение статистики групп"""
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
        """Обновление параметров группы"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        # Обновляем поля
        for key, value in kwargs.items():
            if hasattr(group, key):
                setattr(group, key, value)
        
        # Сохраняем изменения
        self.config_manager.save_groups(self.groups)
        logger.info(f"Группа {group.group_name} обновлена")
        return True
    
    def add_group(self, group_id: int, group_name: str, invite_link: str, 
                  max_daily_invites: int = 100) -> bool:
        """Добавление новой группы"""
        try:
            new_group = self.config_manager.add_group(group_id, group_name, invite_link)
            new_group.max_daily_invites = max_daily_invites
            
            # Перезагружаем список групп
            self.groups = self.config_manager.load_groups()
            logger.info(f"Добавлена новая группа: {group_name}")
            return True
            
        except ValueError as e:
            logger.error(f"Ошибка добавления группы: {e}")
            return False
    
    def remove_group(self, group_id: int) -> bool:
        """Удаление группы"""
        group = self.get_group_by_id(group_id)
        if not group:
            return False
        
        self.groups.remove(group)
        self.config_manager.save_groups(self.groups)
        
        # Также удаляем записи о приглашениях в эту группу
        for user_invites in self.user_invitations.values():
            if group_id in user_invites:
                del user_invites[group_id]
        
        logger.info(f"Группа {group.group_name} удалена")
        return True
    
    def get_user_invitation_history(self, user_id: int) -> Dict[int, float]:
        """Получение истории приглашений пользователя"""
        return self.user_invitations.get(user_id, {})
    
    def validate_group_settings(self) -> List[str]:
        """Валидация настроек групп"""
        issues = []
        
        for group in self.groups:
            # Проверяем наличие ссылки-приглашения
            if not group.invite_link or not group.invite_link.startswith('https://t.me/'):
                issues.append(f"Группа {group.group_name}: некорректная ссылка-приглашение")
            
            # Проверяем назначенные аккаунты
            if group.is_active and not group.assigned_accounts:
                issues.append(f"Группа {group.group_name}: нет назначенных аккаунтов")
            
            # Проверяем лимиты
            if group.max_daily_invites <= 0:
                issues.append(f"Группа {group.group_name}: некорректный лимит приглашений")
        
        return issues