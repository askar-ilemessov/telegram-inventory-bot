#!/bin/bash
# Start Django admin server in Docker container

echo "Starting Django admin server on http://localhost:8000/admin"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "Press Ctrl+C to stop"
echo ""

docker exec -it inventory_pos_bot python manage.py runserver 0.0.0.0:8000

