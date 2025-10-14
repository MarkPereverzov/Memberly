#!/usr/bin/env python3
"""Simple test script to check whitelist functionality and database"""

import sqlite3
import time

def test_whitelist_simple():
    db_path = 'data/bot_database.db'
    
    print("="*60)
    print("WHITELIST DATABASE TEST")
    print("="*60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current whitelist entries
        print("\n1. Current whitelist entries:")
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
        
        # Check users table
        print("\n2. Current users in database:")
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
        
        # Test specific username lookup
        print("\n3. Testing username lookup:")
        test_username = "wxczxo"
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (test_username,))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            print(f"   Found user @{test_username} with ID: {user_id}")
            
            # Check if this user is whitelisted
            cursor.execute('SELECT user_id FROM whitelist WHERE user_id = ? AND is_active = 1', (user_id,))
            whitelist_result = cursor.fetchone()
            is_whitelisted = whitelist_result is not None
            print(f"   Is whitelisted: {is_whitelisted}")
        else:
            print(f"   User @{test_username} not found in database")
            print("   User needs to interact with bot first (send /start)")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_whitelist_simple()