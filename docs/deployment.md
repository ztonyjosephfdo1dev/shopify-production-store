# Deployment Guide

## Manual Deployment

### To Staging (Development Theme)

```bash
# Create/use development theme
shopify theme push -d -u
```

### To Production (Live Theme)

```bash
# IMPORTANT: Always backup first!
shopify theme pull --live -d backups/pre-deploy-$(date +%Y%m%d-%H%M%S)

# Publish your theme to live
shopify theme publish --id <YOUR_THEME_ID>
```

## GitHub Actions (Automated)

Set up `.github/workflows/deploy.yml` for automated deployment:

```yaml
name: Deploy to Shopify

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Shopify CLI
        run: npm install -g @shopify/cli
      
      - name: Deploy to Shopify
        env:
          SHOPIFY_CLI_AUTH_TOKEN: ${{ secrets.SHOPIFY_CLI_AUTH_TOKEN }}
        run: |
          shopify theme push -d -u
```

## Pre-Deployment Checklist

- [ ] All changes tested in development store
- [ ] Code reviewed and approved
- [ ] No console errors in browser dev tools
- [ ] Theme backed up
- [ ] CSS/JavaScript minified
- [ ] Images optimized
- [ ] All links verified
- [ ] Mobile responsive test passed

## Rollback

If issues arise after deployment:

```bash
# Restore previous version from backup
shopify theme push -d backups/pre-deploy-TIMESTAMP

# Or manually revert changes and redeploy
```

## Deployment Schedule

- **Updates**: Deploy during low-traffic hours
- **Hotfixes**: Deploy immediately after testing
- **Major changes**: Schedule maintenance window
