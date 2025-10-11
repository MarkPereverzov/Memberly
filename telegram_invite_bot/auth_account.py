#!/usr/bin/env python3
"""
Separate script to authenticate an account
"""
import asyncio
import os
import sys
from pyrogram import Client

async def authenticate_account():
    """Authenticate Account 2"""
    
    # Account 2 details from accounts.json
    api_id = 23282455
    api_hash = "e38132ee3cca814f1f65b531409652eb"
    phone = "+358468027221"
    session_name = "Account 2"
    
    # Create sessions directory if it doesn't exist
    sessions_dir = os.path.join(os.path.dirname(__file__), "data", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    
    session_file = os.path.join(sessions_dir, f"{session_name}.session")
    
    print(f"Authenticating account: {phone}")
    print(f"Session file: {session_file}")
    
    try:
        client = Client(
            session_file,
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone
        )
        
        await client.start()
        
        # Get user info
        me = await client.get_me()
        print(f"Successfully authenticated: {me.first_name} (@{me.username})")
        
        await client.stop()
        print("Authentication completed successfully!")
        
    except Exception as e:
        print(f"Error during authentication: {e}")

if __name__ == "__main__":
    asyncio.run(authenticate_account())