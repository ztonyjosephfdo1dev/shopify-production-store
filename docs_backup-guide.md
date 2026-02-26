# Backup Guide — Shopify Theme & Settings

Version: 1.0  
Date: 2026-02-25

## Objective
Describe how to backup theme code and key store settings to allow recovery.

## Theme Code Backup
1. Duplicate the live theme in Shopify Admin (Theme actions → Duplicate).
2. Use Shopify CLI to pull and export theme files:
   - shopify theme pull --theme <theme-id> --dir ./backup-theme
3. Commit exported theme files to a timestamped folder in a private repository or store them offsite.
   - mkdir backups && cp -r backup-theme backups/backup-YYYYMMDD
   - git add backups && git commit -m "Backup: YYYY-MM-DD live theme"
4. Store a copy in cloud storage (S3, Google Drive) if desired.

## Settings & Data
- Export product CSV from Shopify (Products → Export).
- Export customer data and orders as needed (Shopify Admin exports).
- Save any app-specific configurations separately.

## Schedule
- Full theme backup: before every production deployment.
- Incremental backups: weekly or after major changes.

## Restore
- To restore theme, either publish the duplicated theme from Shopify Admin or use Shopify CLI push to replace live theme files (test on duplicate first).

## Security
- Store backups in a secure location.
- Do not commit API keys or secrets to backups or repo.