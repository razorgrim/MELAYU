#!/bin/bash

echo "===================================="
echo " AQW MELAYU BOT INSTALLER"
echo "===================================="

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

echo "Starting MariaDB..."

systemctl enable mariadb
systemctl start mariadb

echo "Creating database..."

mysql < schema.sql

echo "Creating data folder..."

mkdir -p data

echo "===================================="
echo " INSTALLATION COMPLETE"
echo "===================================="

echo ""
echo "Next steps:"
echo "1. Edit .env"
echo "2. Put your Discord token"
echo "3. Run:"
echo ""
echo "source venv/bin/activate"
echo "python3 bot.py"