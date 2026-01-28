#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Railway Deployment..."

# Wait for PostgreSQL (Railway uses internal hostname)
echo "⏳ Waiting for PostgreSQL..."
timeout=30
counter=0
until pg_isready -h postgres.railway.internal -p 5432 -U postgres 2>/dev/null || [ $counter -eq $timeout ]; do
  counter=$((counter+1))
  sleep 1
done

if [ $counter -eq $timeout ]; then
  echo "⚠️  PostgreSQL not ready, but continuing anyway (Railway might handle this differently)..."
else
  echo "✅ PostgreSQL is ready!"
fi

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

# Start gunicorn in the background
echo "🌐 Starting Django web server (gunicorn)..."
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --daemon --access-logfile - --error-logfile -

# Give gunicorn a moment to start
sleep 2

# Start the bot in the foreground
echo "🤖 Starting Telegram bot..."
exec python manage.py run_bot

