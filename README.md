# Telegram Invite Bot

An automated bot for inviting users to Telegram groups using user accounts with advanced whitelist management and statistics collection.

## 🚀 Features

- **Automated invitations**: Send invitations to groups through user accounts
- **Multi-account management**: Support for multiple accounts with load balancing
- **Ban protection**: Cooldown system and limits to prevent blocks
- **Advanced whitelist system**: Database-driven user access control with expiration dates
- **Admin panel**: Interactive monitoring and management through Telegram
- **Real-time statistics**: Comprehensive statistics collection and reporting
- **Group management**: Add, remove, and monitor target groups
- **Automated statistics collection**: Periodic collection of group member counts and metrics

## 📋 Requirements

- Python 3.8+
- Telegram Bot Token (from @BotFather)
- API ID and API Hash from https://my.telegram.org
- Telegram user accounts for sending invitations

## 🛠 Installation

1. **Clone repository**
```bash
git clone <repository-url>
cd telegram_invite_bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Setup configuration**
```bash
# Copy configuration examples
cp .env.example .env
cp config/accounts.json.example config/accounts.json
cp config/groups.json.example config/groups.json
```

4. **Fill configuration**

Edit the `.env` file:
```env
BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=123456789,987654321
WHITELIST_USER_IDS=123456789,987654321,555666777
INVITE_COOLDOWN_SECONDS=300
GROUP_COOLDOWN_SECONDS=60
MAX_INVITES_PER_DAY=50
```
```

## ⚙️ Configuration

### User accounts (`config/accounts.json`)

```json
[
  {
    "session_name": "account1",
    "api_id": 12345678,
    "api_hash": "your_api_hash_here",
    "phone": "+1234567890",
    "is_active": true,
    "last_used": 0.0,
    "daily_invites_count": 0,
    "groups_assigned": []
  }
]
```

**Getting API ID and API Hash:**
1. Go to https://my.telegram.org
2. Log into your account
3. Go to "API development tools"
4. Create a new application
5. Copy App api_id and App api_hash

### Groups (`config/groups.json`)

```json
[
  {
    "group_id": -1001234567890,
    "group_name": "Example Group",
    "invite_link": "https://t.me/+xxxxxxxxxx",
    "is_active": true,
    "assigned_accounts": ["account1"],
    "max_daily_invites": 100,
    "current_daily_invites": 0
]
```

**Getting group ID:**
1. Add @userinfobot to the group
2. Send `/id` command in the group
3. Copy the group ID (starts with -100)

## 🚀 Usage

```bash
python main.py
```

## 📱 Bot Commands

### User Commands
- `/start` - Welcome message and information
- `/invite` - Request invitation to a group
- `/status` - Check your status and limits
- `/groups_info` - View groups information and statistics
- `/help` - Help and command reference

### Administrator Commands
- `/admin` - Administrator panel with interactive interface
- `/whitelist <user_id> <days> [username]` - Add user to whitelist
- `/remove_whitelist <user_id>` - Remove user from whitelist
- `/add_group <name> <link>` - Add new group (auto-detects ID by joining)
- `/remove_group <id>` - Remove group
- `/force_stats` - Force statistics collection
- `/block <user_id> [hours]` - Block user
- `/unblock <user_id>` - Unblock user
- `/reset` - Reset daily statistics

## 🎯 New Whitelist System

The bot now features a database-driven whitelist system:

### Features
- **Expiration dates**: Users can be whitelisted for specific periods
- **Admin management**: Admins can add/remove users with commands
- **Automatic cleanup**: Expired entries are automatically removed
- **Access verification**: All commands check whitelist status

### Usage Examples
```bash
# Add user to whitelist for 30 days
/whitelist 123456789 30 @username

# Remove user from whitelist
/remove_whitelist 123456789

# Users can check their status
/status
```

## 📊 Enhanced Statistics

### Real-time Monitoring
- Group member counts collected automatically
- Success/failure rates tracked
- Historical data maintained

### Available via:
- `/admin` → Statistics (for admins)
- `/groups_info` (for whitelisted users)
- `/force_stats` (manual collection for admins)

## 🔒 Security and Limitations

### Cooldown System
- **Users**: 5 minutes between invitation requests
- **Groups**: 1 minute between invitations to same group
- **Daily limits**: 10 invitations per user per day

### Ban Protection
- Automatic load balancing between accounts
- FloodWait error handling
- Temporary deactivation of problematic accounts
- Account activity monitoring

### Access Control
- User whitelist
- Administrator roles
- Spammer blocking

## 📁 Project Structure

```
telegram_invite_bot/
├── main.py                 # Main launch file
├── requirements.txt        # Dependencies
├── .env.example           # Environment variables example
├── README.md              # Documentation
├── config/                # Configuration files
│   ├── config.py          # Configuration classes
│   ├── accounts.json      # User accounts
│   ├── groups.json        # Target groups
│   └── *.example          # Configuration examples
├── src/                   # Source code
│   ├── account_manager.py # Account management
│   ├── group_manager.py   # Group management
│   ├── cooldown_manager.py# Cooldown system
│   ├── database_manager.py# Database operations
│   ├── whitelist_manager.py# Whitelist management
│   └── group_stats_collector.py# Statistics collection
├── data/                  # Data and cache
│   ├── sessions/          # Pyrogram sessions
│   ├── cooldowns.json     # Cooldown data
│   └── bot_database.db    # SQLite database
└── logs/                  # Logs
    └── bot.log
```

## 🔧 Initial Setup

### 1. Creating the Bot
1. Message @BotFather in Telegram
2. Create a new bot with `/newbot` command
3. Save the received token

### 2. Adding Accounts
1. Get API credentials from my.telegram.org
2. Add accounts to `config/accounts.json`
3. Enter confirmation code on first run

### 3. Setting up Groups
1. Get target group IDs
2. Create invitation links
3. Add groups to `config/groups.json`
4. Assign accounts to groups

### 4. Testing
1. Add your ID to the whitelist with `/whitelist` command
2. Start the bot
3. Test the `/invite` command

## 📊 Monitoring and Statistics

### Database
- User whitelist with expiration tracking
- Invitation history and success rates
- Group statistics and member counts
- Automated cleanup of old records

### Logs
All events are recorded in `logs/bot.log`:
- Successful/failed invitations
- Account errors
- User activity

### Statistics
Available through admin panel (`/admin` → Statistics):
- Number of active accounts
- Invitation statistics
- Blocked users

### Statistics Access
- **Admin panel**: Access via `/admin` → Statistics
- **User info**: Available via `/groups_info` for whitelisted users
- **Force collection**: Manual update with `/force_stats`

## ⚠️ Important Notes

1. **Legality**: Ensure usage complies with Telegram ToS
2. **Limits**: Don't exceed reasonable invitation limits
3. **Accounts**: Use real accounts with history
4. **Groups**: Ensure accounts are members of target groups
5. **Database**: Regular backups recommended for `data/bot_database.db`

## 🐛 Troubleshooting

### Account won't connect
- Check API ID and API Hash
- Verify phone number format
- Check if account is banned

### FloodWait errors
- Reduce invitation frequency
- Add more accounts
- Increase cooldowns

### User doesn't receive invitations
- Check recipient's privacy settings
- Ensure account can message the user
- Verify sender isn't blocked

### Database issues
- Check file permissions for `data/` directory
- Verify SQLite installation
- Check disk space

## 📞 Support

When experiencing issues:
1. Check logs in `logs/bot.log`
2. Verify configuration files
3. Test with `/force_stats` command
4. Check database integrity
3. Check account status via `/admin`

## 📄 License

This project is intended for educational purposes. Make sure your usage complies with Telegram's Terms of Service.