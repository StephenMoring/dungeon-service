#!/bin/sh
# Nightly database backup. Writes backups/dungeon-YYYY-MM-DD.sql.gz next to this
# script and keeps the last 7. Copy them off the server too (see DEPLOY.md): a backup
# on the same disk doesn't survive losing the server.
#   crontab -e   then add:   15 3 * * * /home/deploy/dungeon-service/infra/prod/backup.sh
set -eu
cd "$(dirname "$0")"
mkdir -p backups
. ./.env
out="backups/dungeon-$(date +%F).sql.gz"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d dungeon | gzip > "$out.tmp"
mv "$out.tmp" "$out"
# Keep a week: remove dumps older than 7 days (only files this script wrote).
find backups -name 'dungeon-*.sql.gz' -mtime +7 -delete
echo "Backed up to $out"
