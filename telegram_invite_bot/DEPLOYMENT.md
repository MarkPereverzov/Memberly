# Deployment Guide for DigitalOcean VPS

## Prerequisites

- DigitalOcean account
- Domain name (optional, but recommended)
- SSH access to your VPS
- Docker and Docker Compose installed on VPS

## Step 1: Setup VPS on DigitalOcean

1. **Create a Droplet:**
   - Go to DigitalOcean Dashboard
   - Click "Create" → "Droplets"
   - Choose Ubuntu 22.04 LTS
   - Select plan (Basic $6/month is sufficient for small bots)
   - Choose datacenter region closest to your users
   - Add SSH key for authentication
   - Create Droplet

2. **Connect to VPS:**
   ```bash
   ssh root@your_droplet_ip
   ```

## Step 2: Install Docker and Docker Compose

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose -y

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Verify installation
docker --version
docker-compose --version
```

## Step 3: Prepare Bot Files

1. **Create application directory:**
   ```bash
   mkdir -p /opt/memberly-bot
   cd /opt/memberly-bot
   ```

2. **Transfer files to VPS:**
   
   From your local machine:
   ```bash
   # Using SCP
   scp -r /path/to/telegram_invite_bot/* root@your_droplet_ip:/opt/memberly-bot/
   
   # Or using rsync (recommended)
   rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
         /path/to/telegram_invite_bot/ root@your_droplet_ip:/opt/memberly-bot/
   ```
   
   Or clone from Git (if you have a repository):
   ```bash
   git clone https://github.com/MarkPereverzov/Memberly /opt/memberly-bot
   cd /opt/memberly-bot/telegram_invite_bot
   ```

3. **Setup environment variables:**
   ```bash
   cd /opt/memberly-bot
   cp .env.example .env
   nano .env
   ```
   
   Edit `.env` with your actual values:
   ```env
   BOT_TOKEN=your_actual_bot_token
   ADMIN_USER_IDS=your_telegram_user_id
   WHITELIST_USER_IDS=
   INVITE_COOLDOWN_SECONDS=180
   GROUP_COOLDOWN_SECONDS=3
   ```

## Step 4: Build and Run with Docker

1. **Build Docker image:**
   ```bash
   docker-compose build
   ```

2. **Start the bot:**
   ```bash
   docker-compose up -d
   ```

3. **Check if running:**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

## Step 5: Manage the Bot

### View logs:
```bash
docker-compose logs -f telegram-bot
```

### Stop the bot:
```bash
docker-compose stop
```

### Restart the bot:
```bash
docker-compose restart
```

### Update the bot:
```bash
# Pull latest code (if using Git)
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Clear database:
```bash
# Enter container
docker-compose exec telegram-bot python clear_database.py
```

## Step 6: Setup Auto-start on System Reboot

Docker Compose with `restart: unless-stopped` will automatically restart the bot after VPS reboot.

Verify:
```bash
sudo reboot
# After reboot, check:
docker-compose ps
```

## Step 7: Setup Firewall (Optional but Recommended)

```bash
# Install UFW
sudo apt install ufw -y

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (if you plan to add a web interface later)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

## Step 8: Monitoring and Maintenance

### Check disk space:
```bash
df -h
```

### Check Docker resource usage:
```bash
docker stats
```

### View bot logs:
```bash
tail -f /opt/memberly-bot/logs/bot.log
```

### Backup data:
```bash
# Backup database and sessions
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/

# Download to local machine
scp root@your_droplet_ip:/opt/memberly-bot/backup-*.tar.gz ./
```

### Clean up Docker resources:
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove everything unused
docker system prune -a
```

## Troubleshooting

### Bot not starting:
```bash
# Check logs
docker-compose logs telegram-bot

# Check if container is running
docker ps -a

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database issues:
```bash
# Enter container shell
docker-compose exec telegram-bot /bin/bash

# Check database file
ls -la /app/data/

# Run database clear script
python clear_database.py
```

### Permission issues:
```bash
# Fix ownership
sudo chown -R root:root /opt/memberly-bot
sudo chmod -R 755 /opt/memberly-bot
```

## Security Best Practices

1. **Use SSH keys instead of passwords**
2. **Keep system updated:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
3. **Use strong passwords for admin accounts**
4. **Regularly backup your data**
5. **Monitor logs for suspicious activity**
6. **Don't expose unnecessary ports**
7. **Use environment variables for sensitive data**

## Cost Estimation

- **Basic Droplet ($6/month):** Suitable for small to medium bots
- **Standard Droplet ($12/month):** Better performance, more users
- **Backups (+20% of Droplet cost):** Recommended for production

## Support and Updates

For issues and updates:
- Check logs: `docker-compose logs -f`
- Monitor resource usage: `docker stats`
- Update regularly: `git pull && docker-compose restart`

---

**🚀 Your bot is now running 24/7 on DigitalOcean!**
