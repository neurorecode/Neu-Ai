#!/usr/bin/env bash
# Nightly Postgres backup with 14-day rotation.
# Install on the VPS crontab:  0 3 * * *  /path/to/Neu-Ai/deploy/backup.sh
set -euo pipefail

cd "$(dirname "$0")"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d-%H%M%S)
docker compose exec -T db pg_dump -U neu -d neu | gzip > "$BACKUP_DIR/neu-$STAMP.sql.gz"

# Keep the newest 14 backups
ls -1t "$BACKUP_DIR"/neu-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm --

echo "Backup written: $BACKUP_DIR/neu-$STAMP.sql.gz"
# Optional off-site copy (uncomment after `rclone config`):
# rclone copy "$BACKUP_DIR" remote:neu-backups
