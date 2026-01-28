#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Railway Deployment with Honcho..."

echo "📦 Running migrations..."
python manage.py migrate --noinput

echo "👤 Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('✅ Superuser created')
else:
    print('✅ Superuser already exists')
" || true

echo "📊 Collecting static files..."
python manage.py collectstatic --noinput || true

echo "🚀 Starting web server and bot with Honcho..."
exec honcho start

