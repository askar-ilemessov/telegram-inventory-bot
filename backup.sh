#!/bin/bash
# Database backup script for production

set -e

BACKUP_DIR="/opt/inventory-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

echo "🔄 Creating database backup..."

# Backup database
docker exec inventory_pos_db pg_dump -U postgres inventory_pos_db > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

echo "✅ Backup created: ${BACKUP_FILE}.gz"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "🧹 Old backups cleaned up"
echo "📊 Current backups:"
ls -lh $BACKUP_DIR/backup_*.sql.gz 2>/dev/null || echo "No backups found"

