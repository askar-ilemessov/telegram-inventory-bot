#!/bin/bash
# Deployment script for VPS

set -e

echo "🚀 Inventory POS Bot - Deployment Script"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Variables
APP_DIR="/opt/inventory-bot"
REPO_URL="${1:-}"

# Check if repo URL provided
if [ -z "$REPO_URL" ]; then
    echo "Usage: sudo ./deploy.sh <git-repo-url>"
    echo "Example: sudo ./deploy.sh https://github.com/username/inventory-bot.git"
    exit 1
fi

echo "📦 Step 1: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

echo ""
echo "📦 Step 2: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt install -y docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

echo ""
echo "📁 Step 3: Creating application directory..."
mkdir -p $APP_DIR
cd $APP_DIR

echo ""
echo "📥 Step 4: Cloning repository..."
if [ -d ".git" ]; then
    echo "Repository already exists, pulling latest changes..."
    git pull
else
    git clone $REPO_URL .
fi

echo ""
echo "🔐 Step 5: Generating secure credentials..."
SECRET_KEY=$(openssl rand -base64 32)
DB_PASSWORD=$(openssl rand -base64 16)

echo ""
echo "📝 Step 6: Creating production environment file..."
read -p "Enter your server IP or domain: " SERVER_HOST
read -p "Enter your Telegram Bot Token: " BOT_TOKEN

cat > .env.docker <<EOF
# Production Environment - Generated $(date)
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$SERVER_HOST,localhost,127.0.0.1

DB_NAME=inventory_pos_db
DB_USER=postgres
DB_PASSWORD=$DB_PASSWORD
DB_HOST=db
DB_PORT=5432

TELEGRAM_BOT_TOKEN=$BOT_TOKEN

GOOGLE_SHEETS_ENABLED=False
EOF

chmod 600 .env.docker
echo "✅ Environment file created"

echo ""
echo "🐳 Step 7: Starting Docker containers..."
docker-compose down 2>/dev/null || true
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

echo ""
echo "👤 Step 8: Creating admin user..."
read -p "Enter admin username: " ADMIN_USER
read -p "Enter your Telegram ID (get from @userinfobot): " TELEGRAM_ID

docker exec -it inventory_pos_bot python manage.py shell -c "
from apps.core.models import StaffProfile
from django.contrib.auth.models import User

user, created = User.objects.get_or_create(
    username='$ADMIN_USER',
    defaults={'first_name': 'Admin', 'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('admin123')
    user.save()
    print('✅ User created: $ADMIN_USER')
else:
    print('ℹ️  User already exists: $ADMIN_USER')

profile, created = StaffProfile.objects.get_or_create(
    user=user,
    defaults={'telegram_id': $TELEGRAM_ID}
)
if created:
    print('✅ Telegram ID linked: $TELEGRAM_ID')
else:
    print('ℹ️  Telegram ID already linked')
"

echo ""
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "📊 Access Django Admin:"
echo "   http://$SERVER_HOST:8000/admin"
echo "   Username: $ADMIN_USER"
echo "   Password: admin123"
echo ""
echo "🤖 Telegram Bot:"
echo "   Send /start to your bot"
echo ""
echo "📝 Useful Commands:"
echo "   View logs:    docker logs inventory_pos_bot -f"
echo "   Restart:      docker-compose restart"
echo "   Stop:         docker-compose down"
echo "   Update:       git pull && docker-compose up -d --build"
echo ""
echo "⚠️  IMPORTANT: Change admin password after first login!"
echo ""

