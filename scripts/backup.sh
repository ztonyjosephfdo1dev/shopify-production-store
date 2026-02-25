#!/bin/bash
# Backup script for Shopify theme

set -e

DATESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/backup-$DATESTAMP"

echo "[$(date)] Starting backup..."
echo "Backup directory: $BACKUP_DIR"

if ! command -v shopify &> /dev/null; then
    echo "ERROR: Shopify CLI is not installed"
    exit 1
fi

shopify theme pull --live -d "$BACKUP_DIR"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup completed successfully"
    echo "Backup saved to: $BACKUP_DIR"
else
    echo "[$(date)] ERROR: Backup failed"
    exit 1
fi
