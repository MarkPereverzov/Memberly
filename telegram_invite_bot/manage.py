#!/usr/bin/env python3
"""
Скрипт для управления ботом-приглашающим
"""
import os
import sys
import asyncio
import json
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import ConfigManager

def setup_project():
    """Первоначальная настройка проекта"""
    print("🛠 Настройка проекта...")
    
    # Создаем необходимые директории
    directories = ["logs", "data", "data/sessions", "config"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Создана директория: {directory}")
    
    # Проверяем наличие конфигурационных файлов
    config_files = {
        ".env": ".env.example",
        "config/accounts.json": "config/accounts.json.example",
        "config/groups.json": "config/groups.json.example"
    }
    
    for target, source in config_files.items():
        if not os.path.exists(target) and os.path.exists(source):
            import shutil
            shutil.copy(source, target)
            print(f"✅ Скопирован файл конфигурации: {target}")
        elif not os.path.exists(target):
            print(f"⚠️  Не найден файл: {target}")
    
    print("\n📝 Не забудьте отредактировать конфигурационные файлы:")
    print("   - .env (токен бота, ID пользователей)")
    print("   - config/accounts.json (пользовательские аккаунты)")
    print("   - config/groups.json (целевые группы)")

def check_config():
    """Проверка конфигурации"""
    print("🔍 Проверка конфигурации...")
    
    # Проверяем .env файл
    if not os.path.exists(".env"):
        print("❌ Файл .env не найден")
        return False
    
    # Проверяем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["BOT_TOKEN", "ADMIN_USER_IDS", "WHITELIST_USER_IDS"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        return False
    
    # Проверяем конфигурационные файлы
    try:
        config_manager = ConfigManager()
        accounts = config_manager.load_accounts()
        groups = config_manager.load_groups()
        
        print(f"✅ Загружено аккаунтов: {len(accounts)}")
        print(f"✅ Загружено групп: {len(groups)}")
        
        if not accounts:
            print("⚠️  Не настроено ни одного аккаунта")
        
        if not groups:
            print("⚠️  Не настроено ни одной группы")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return False

def add_account():
    """Добавление нового аккаунта"""
    print("➕ Добавление нового аккаунта...")
    
    try:
        session_name = input("Введите имя сессии: ").strip()
        api_id = int(input("Введите API ID: ").strip())
        api_hash = input("Введите API Hash: ").strip()
        phone = input("Введите номер телефона: ").strip()
        
        config_manager = ConfigManager()
        account = config_manager.add_account(session_name, api_id, api_hash, phone)
        
        print(f"✅ Аккаунт {session_name} добавлен успешно")
        
    except ValueError as e:
        print(f"❌ Ошибка: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

def add_group():
    """Добавление новой группы"""
    print("➕ Добавление новой группы...")
    
    try:
        group_id = int(input("Введите ID группы (например, -1001234567890): ").strip())
        group_name = input("Введите название группы: ").strip()
        invite_link = input("Введите ссылку-приглашение: ").strip()
        
        config_manager = ConfigManager()
        group = config_manager.add_group(group_id, group_name, invite_link)
        
        print(f"✅ Группа {group_name} добавлена успешно")
        
    except ValueError as e:
        print(f"❌ Ошибка: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

def show_stats():
    """Показать статистику"""
    print("📊 Статистика конфигурации...")
    
    try:
        config_manager = ConfigManager()
        accounts = config_manager.load_accounts()
        groups = config_manager.load_groups()
        
        print(f"\n📱 Аккаунты ({len(accounts)}):")
        for account in accounts:
            status = "✅" if account.is_active else "❌"
            print(f"  {status} {account.session_name} ({account.phone})")
        
        print(f"\n🏢 Группы ({len(groups)}):")
        for group in groups:
            status = "✅" if group.is_active else "❌"
            print(f"  {status} {group.group_name} (ID: {group.group_id})")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def test_accounts():
    """Тестирование подключения аккаунтов"""
    print("🧪 Тестирование аккаунтов...")
    
    try:
        from src.account_manager import AccountManager
        
        config_manager = ConfigManager()
        account_manager = AccountManager(config_manager)
        
        await account_manager.initialize()
        
        print("✅ Все аккаунты протестированы")
        
        await account_manager.shutdown()
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")

def run_bot():
    """Запуск бота"""
    print("🚀 Запуск бота...")
    
    # Проверяем конфигурацию перед запуском
    if not check_config():
        print("❌ Конфигурация некорректна. Исправьте ошибки и попробуйте снова.")
        return
    
    # Запускаем основной скрипт
    os.system("python main.py")

def main():
    """Главное меню"""
    while True:
        print("\n" + "="*50)
        print("🤖 Telegram Invite Bot - Управление")
        print("="*50)
        print("1. 🛠  Первоначальная настройка")
        print("2. 🔍 Проверить конфигурацию")
        print("3. ➕ Добавить аккаунт")
        print("4. ➕ Добавить группу")
        print("5. 📊 Показать статистику")
        print("6. 🧪 Тестировать аккаунты")
        print("7. 🚀 Запустить бота")
        print("8. 🚪 Выход")
        print("="*50)
        
        choice = input("Выберите действие (1-8): ").strip()
        
        if choice == "1":
            setup_project()
        elif choice == "2":
            check_config()
        elif choice == "3":
            add_account()
        elif choice == "4":
            add_group()
        elif choice == "5":
            show_stats()
        elif choice == "6":
            asyncio.run(test_accounts())
        elif choice == "7":
            run_bot()
        elif choice == "8":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Попробуйте снова.")
        
        input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    main()