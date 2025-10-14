#!/usr/bin/env python3
"""Test script to check whitelist functionality and database"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager import DatabaseManager
from src.whitelist_manager import WhitelistManager

def test_whitelist():
    # Initialize managers
    db_manager = DatabaseManager('data/bot_database.db')
    whitelist_manager = WhitelistManager(db_manager, [7397516151])  # Your admin ID
    
    print("="*60)
    print("WHITELIST DATABASE TEST")
    print("="*60)
    
    # Check current whitelist entries
    print("\n1. Current whitelist entries:")
    try:
        with db_manager.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, expiration_date, added_by, is_active 
                FROM whitelist 
                ORDER BY added_date DESC
            ''')
            entries = cursor.fetchall()
            
            if entries:
                for entry in entries:
                    user_id, username, exp_date, added_by, is_active = entry
                    status = "Active" if is_active else "Inactive"
                    print(f"   User ID: {user_id}, Username: {username}, Status: {status}")
                    print(f"   Expiration: {exp_date}, Added by: {added_by}")
            else:
                print("   No whitelist entries found")
    except Exception as e:
        print(f"   Error reading whitelist: {e}")
    
    # Check users table
    print("\n2. Current users in database:")
    try:
        with db_manager.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, last_name 
                FROM users 
                ORDER BY last_interaction DESC
            ''')
            users = cursor.fetchall()
            
            if users:
                for user in users:
                    user_id, username, first_name, last_name = user
                    full_name = f"{first_name or ''} {last_name or ''}".strip()
                    print(f"   ID: {user_id}, @{username}, Name: {full_name}")
            else:
                print("   No users found in database")
    except Exception as e:
        print(f"   Error reading users: {e}")
    
    # Test specific username lookup
    print("\n3. Testing username lookup:")
    test_username = "wxczxo"
    user_id = db_manager.get_user_id_by_username(test_username)
    if user_id:
        print(f"   Found user @{test_username} with ID: {user_id}")
        
        # Check if this user is whitelisted
        is_whitelisted = whitelist_manager.is_user_whitelisted(user_id)
        print(f"   Is whitelisted: {is_whitelisted}")
    else:
        print(f"   User @{test_username} not found in database")
        print("   User needs to interact with bot first (send /start)")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_whitelist()