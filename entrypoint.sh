#!/bin/bash

# Exit on error
set -e

# Skip database wait on Railway (pg_isready doesn't work with Railway's internal networking)
if [ "$SKIP_DB_WAIT" = "true" ]; then
  echo "Skipping PostgreSQL wait check (SKIP_DB_WAIT=true)"
else
  echo "Waiting for PostgreSQL..."
  while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
    sleep 1
  done
  echo "PostgreSQL is ready!"
fi

echo "Running migrations..."
# python manage.py migrate --noinput

echo "Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created')
else:
    print('Superuser already exists')
" || true

# Execute the CMD passed from docker-compose
echo "Starting: $@"
exec "$@"

