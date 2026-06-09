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

echo "Installing Python requirements..."
pip3 install --upgrade pip --break-system-packages || pip3 install --upgrade pip
pip3 install -r requirements.txt --break-system-packages || pip3 install -r requirements.txt

echo "Installing Playwright chromium browser..."
playwright install chromium

echo "Starting MariaDB..."
systemctl enable mariadb
systemctl start mariadb

# Load environment variables from .env if it exists
if [ -f .env ]; then
  echo "Loading existing configuration from .env..."
  export $(grep -v '^#' .env | xargs)
fi

# Set default MySQL connection details if not set
DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-3306}
DB_USER=${DB_USER:-root}
DB_PASSWORD=${DB_PASSWORD:-}
DB_NAME=${DB_NAME:-melayu_bot}

# Build mysql command line arguments
MYSQL_ARGS="-h $DB_HOST -P $DB_PORT -u $DB_USER"
if [ ! -z "$DB_PASSWORD" ]; then
  MYSQL_ARGS="$MYSQL_ARGS -p$DB_PASSWORD"
fi

echo "Creating database '$DB_NAME'..."
mysql $MYSQL_ARGS -e "CREATE DATABASE IF NOT EXISTS $DB_NAME DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql $MYSQL_ARGS $DB_NAME < schema.sql

echo "Creating data folder..."
mkdir -p data

echo "Setting up environment file..."
if [ ! -f .env ]; then
  cp .env.example .env
  # Update DB config in .env to default
  sed -i "s/DB_HOST=localhost/DB_HOST=$DB_HOST/g" .env
  sed -i "s/DB_PORT=3306/DB_PORT=$DB_PORT/g" .env
  sed -i "s/DB_USER=your_db_username/DB_USER=$DB_USER/g" .env
  sed -i "s/DB_PASSWORD=your_db_password/DB_PASSWORD=$DB_PASSWORD/g" .env
  sed -i "s/DB_NAME=your_db_name/DB_NAME=$DB_NAME/g" .env
  echo "Created .env file configured with database credentials."
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
echo "4. Use '!setup help' inside Discord to configure leveling, shop, and tickets."