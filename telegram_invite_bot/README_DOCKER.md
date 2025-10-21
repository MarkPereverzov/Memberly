# Docker Deployment Guide

## Quick Start (Local Testing)

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   nano .env  # or use any text editor
   ```

3. **Build and run:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Stop:**
   ```bash
   docker-compose down
   ```

## Commands

### Build
```bash
docker-compose build
```

### Start
```bash
docker-compose up -d
```

### Stop
```bash
docker-compose down
```

### Restart
```bash
docker-compose restart
```

### View logs
```bash
docker-compose logs -f
docker-compose logs -f --tail=100
```

### Execute commands inside container
```bash
docker-compose exec telegram-bot /bin/bash
docker-compose exec telegram-bot python clear_database.py
```

### Clean up
```bash
# Remove containers and volumes
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Clean everything
docker system prune -a
```

## File Structure

```
telegram_invite_bot/
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore          # Files to exclude from Docker build
├── .env.example           # Environment variables template
├── .env                   # Your actual environment variables (git-ignored)
├── requirements.txt       # Python dependencies
├── main.py               # Bot entry point
├── clear_database.py     # Database cleanup script
├── data/                 # Persistent data (mounted as volume)
│   ├── bot_database.db
│   └── sessions/
├── logs/                 # Log files (mounted as volume)
└── config/              # Configuration files (mounted as volume)
```

## Environment Variables

Required in `.env`:
- `BOT_TOKEN` - Your Telegram Bot API token
- `ADMIN_USER_IDS` - Comma-separated list of admin Telegram user IDs
- `WHITELIST_USER_IDS` - Comma-separated list of whitelisted user IDs (optional)
- `INVITE_COOLDOWN_SECONDS` - Cooldown between invitations (default: 180)
- `GROUP_COOLDOWN_SECONDS` - Cooldown between group invitations (default: 3)

## Volumes

The following directories are mounted as volumes for data persistence:
- `./data` → `/app/data` - Database and session files
- `./logs` → `/app/logs` - Log files
- `./config` → `/app/config` - Configuration files

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed DigitalOcean VPS deployment instructions.

## Troubleshooting

### Container won't start
```bash
docker-compose logs telegram-bot
docker-compose ps -a
```

### Database locked error
```bash
docker-compose down
rm data/bot_database.db-journal
docker-compose up -d
```

### Permission denied
```bash
sudo chown -R $USER:$USER data/ logs/ config/
```

### Out of disk space
```bash
docker system df
docker system prune -a
```

## Updating

```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Backup

```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/

# Restore
tar -xzf backup-YYYYMMDD.tar.gz
```
