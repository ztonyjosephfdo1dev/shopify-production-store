# Backup Strategy

## Automated Backups

### Using cron (macOS/Linux)

Create a daily backup script:

```bash
#!/bin/bash
# backup.sh

DATESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/backup-$DATESTAMP"

echo "Creating backup: $BACKUP_DIR"
shopify theme pull --live -d "$BACKUP_DIR"

echo "Backup completed successfully"
```

Schedule with cron:
```bash
# Run backup daily at 2 AM
0 2 * * * cd /path/to/repo && ./scripts/backup.sh
```

### Using PowerShell (Windows)

```powershell
# backup.ps1
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = "backups/backup-$timestamp"

Write-Host "Creating backup: $backupDir"
shopify theme pull --live -d $backupDir

Write-Host "Backup completed successfully"
```

Schedule with Task Scheduler:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger for daily at 2 AM
4. Set action to run PowerShell script

## Manual Backups

Before any major deployment or change:

```bash
# Full theme backup
shopify theme pull --live -d backups/manual-$(date +%Y%m%d-%H%M%S)
```

## Backup Retention

- Keep backups for at least **30 days**
- Archive older backups separately
- Test restore procedures quarterly
- Document any issues found during testing

## Recovery Process

### To Restore from Backup

```bash
# List available backups
ls -la backups/

# Restore to development theme first
shopify theme push -d backups/backup-TIMESTAMP

# After testing, publish to live
shopify theme publish --id <BACKUP_THEME_ID>
```

### Emergency Recovery

If the live theme is corrupted:

1. Create a new empty theme: `shopify theme create`
2. Push backup to it: `shopify theme push -d backups/backup-TIMESTAMP --theme-id <NEW_THEME_ID>`
3. Publish the restored theme: `shopify theme publish --id <NEW_THEME_ID>`
4. Test thoroughly before confirming

## Storage

- Store backups in `/backups` directory
- Commit backups to Git (use `.gitattributes` for large files if needed)
- Consider cloud storage (AWS S3, Google Cloud Storage) for critical backups

## Disaster Recovery Plan

1. **Detection**: Monitor theme errors in Shopify admin
2. **Assessment**: Check latest backup status
3. **Communication**: Notify team members
4. **Recovery**: Follow recovery process above
5. **Verification**: Test all critical pages
6. **Documentation**: Record incident details
