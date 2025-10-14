#!/usr/bin/env python3
"""Simple test remove whitelist functionality"""

import sqlite3

def simple_test_remove_whitelist():
    db_path = 'data/bot_database.db'
    
    print("="*60)
    print("REMOVE WHITELIST TEST (SIMPLE)")
    print("="*60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current whitelist entries
        print("\n1. Current whitelist entries:")
        cursor.execute('''
            SELECT w.user_id, w.username, u.username as real_username, w.expiration_date, w.is_active 
            FROM whitelist w
            LEFT JOIN users u ON w.user_id = u.user_id
            ORDER BY w.added_date DESC
        ''')
        entries = cursor.fetchall()
        
        if entries:
            for entry in entries:
                user_id, w_username, real_username, exp_date, is_active = entry
                status = "Active" if is_active else "Inactive"
                print(f"   User ID: {user_id}, Whitelist Username: {w_username}, Real Username: @{real_username}, Status: {status}")
        else:
            print("   No whitelist entries found")
        
        # Test specific username lookup
        print("\n2. Testing username lookup for wxczxo:")
        cursor.execute('SELECT user_id FROM users WHERE username = ?', ('wxczxo',))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            print(f"   Found user @wxczxo with ID: {user_id}")
            
            # Check if this user is whitelisted
            cursor.execute('SELECT user_id, expiration_date FROM whitelist WHERE user_id = ? AND is_active = 1', (user_id,))
            whitelist_result = cursor.fetchone()
            if whitelist_result:
                print(f"   ✅ User is currently whitelisted (expires: {whitelist_result[1]})")
            else:
                print(f"   ❌ User is NOT whitelisted")
        else:
            print(f"   User @wxczxo not found in database")
        
        # Check all users
        print("\n3. All users in database:")
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
                
                # Check if user is whitelisted
                cursor.execute('SELECT 1 FROM whitelist WHERE user_id = ? AND is_active = 1', (user_id,))
                is_whitelisted = cursor.fetchone() is not None
                status = "✅ Whitelisted" if is_whitelisted else "❌ Not whitelisted"
                print(f"      Status: {status}")
        else:
            print("   No users found in database")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)

if __name__ == "__main__":
    simple_test_remove_whitelist()