#!/bin/bash

echo "===================================="
echo " AQW MELAYU BOT INSTALLER"
echo "===================================="

# Update system packages
apt update && apt upgrade -y

echo "Installing system packages..."
apt install -y \
python3 \
python3-pip \
python3-venv \
mariadb-server \
git

echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing Python requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing Playwright chromium browser..."
playwright install chromium

echo "Starting MariaDB..."
systemctl enable mariadb
systemctl start mariadb

echo "Creating database 'melayu_bot'..."
mysql -e "CREATE DATABASE IF NOT EXISTS melayu_bot DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql melayu_bot < schema.sql
mysql melayu_bot < classes.sql

echo "Creating data folder..."
mkdir -p data

echo "Setting up environment file..."
if [ ! -f .env ]; then
  cp .env.example .env
  # Update DB_NAME in .env to the default melayu_bot
  sed -i 's/DB_NAME=your_db_name/DB_NAME=melayu_bot/g' .env
  sed -i 's/DB_USER=your_db_username/DB_USER=root/g' .env
  sed -i 's/DB_PASSWORD=your_db_password/DB_PASSWORD=/g' .env
  echo "Created .env file configured for local MariaDB (melayu_bot database, user root, no password)."
fi

echo "===================================="
echo " INSTALLATION COMPLETE"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Edit .env and put your Discord bot token (DISCORD_TOKEN)"
echo "2. Edit panel configurations in panel_config.py or emojis in emojis.py if needed."
echo "3. Run the bot using:"
echo "   ./start.sh"