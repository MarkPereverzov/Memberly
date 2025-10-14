#!/usr/bin/env python3
"""Check both database files"""

import sqlite3
import os

def check_both_databases():
    databases = [
        'data/bot_database.db',
        '../data/bot_database.db'
    ]
    
    for db_path in databases:
        print("="*60)
        print(f"CHECKING DATABASE: {db_path}")
        print("="*60)
        
        if not os.path.exists(db_path):
            print(f"   Database file {db_path} does not exist")
            continue
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check whitelist entries
            print("\n1. Whitelist entries:")
            cursor.execute('''
                SELECT w.user_id, w.username, w.expiration_date, w.is_active 
                FROM whitelist w
                ORDER BY w.added_date DESC
            ''')
            entries = cursor.fetchall()
            
            if entries:
                for entry in entries:
                    user_id, username, exp_date, is_active = entry
                    status = "Active" if is_active else "Inactive"
                    print(f"   User ID: {user_id}, Username: {username}, Status: {status}")
            else:
                print("   No whitelist entries found")
            
            # Check users
            print("\n2. Users:")
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
                print("   No users found")
            
            conn.close()
            
        except Exception as e:
            print(f"   Error reading {db_path}: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    check_both_databases()