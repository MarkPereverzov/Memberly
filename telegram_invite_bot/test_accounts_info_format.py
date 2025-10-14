#!/usr/bin/env python3
"""Test script for /accounts_info command formatting"""

# Simulate account data that would come from get_detailed_account_stats()
simulated_accounts_data = {
    'total_accounts': 3,
    'active_accounts': 2,
    'connected_accounts': 2,
    'accounts_details': [
        {
            'session_name': 'Account 1',
            'phone': '+1234567890',
            'is_active': True,
            'is_connected': True,
            'user_id': 123456789,
            'username': 'user1',
            'first_name': 'John'
        },
        {
            'session_name': 'Account 2',
            'phone': '+0987654321',
            'is_active': True,
            'is_connected': True,
            'user_id': 987654321,
            'username': 'user2',
            'first_name': 'Jane'
        },
        {
            'session_name': 'Account 3',
            'phone': '+1122334455',
            'is_active': False,
            'is_connected': False,
            'user_id': 'Unknown',
            'username': 'Unknown',
            'first_name': 'Unknown'
        }
    ]
}

def format_accounts_info(account_stats):
    """Format accounts info according to the new specification"""
    # Build response according to the new format
    response_lines = ["🔄 Accounts Information (Updated)\n"]
    
    successful_accounts = 0
    failed_accounts = 0
    
    if account_stats['accounts_details']:
        for account in account_stats['accounts_details']:
            account_name = account['session_name']
            account_id = account.get('user_id', 'Unknown')
            
            if account.get('is_active', False) and account.get('is_connected', False):
                status_icon = "✅"
                successful_accounts += 1
            else:
                status_icon = "❌"
                failed_accounts += 1
            
            response_lines.append(f"{status_icon} {account_name} (ID: {account_id})")
    else:
        response_lines.append("❌ No accounts found")
        failed_accounts = 1
    
    # Add summary
    total_accounts = successful_accounts + failed_accounts
    response_lines.append("")
    response_lines.append("📈 Update Summary:")
    response_lines.append(f"• ✅ Successfully: {successful_accounts} accounts")
    response_lines.append(f"• ❌ Failed: {failed_accounts} accounts")
    response_lines.append(f"• 📊 Total: {total_accounts}")
    
    return "\n".join(response_lines)

if __name__ == "__main__":
    print("="*50)
    print("PREVIEW OF NEW /accounts_info OUTPUT:")
    print("="*50)
    
    formatted_output = format_accounts_info(simulated_accounts_data)
    print(formatted_output)
    
    print("="*50)
    print("Testing with empty accounts...")
    print("="*50)
    
    empty_data = {
        'total_accounts': 0,
        'active_accounts': 0,
        'connected_accounts': 0,
        'accounts_details': []
    }
    
    empty_output = format_accounts_info(empty_data)
    print(empty_output)
    
    print("="*50)