# Shopify Setup Guide

## Prerequisites

1. Shopify account with admin access
2. Shopify CLI installed
3. Git installed
4. Node.js 14+ installed

## Step 1: Install Shopify CLI

Download and install from [Shopify CLI](https://shopify.dev/docs/themes/tools/cli)

## Step 2: Authenticate

```bash
shopify auth login
```

Follow the prompts to authorize with your Shopify account.

## Step 3: Pull Existing Theme

```bash
# List all available themes
shopify theme list

# Pull the live/published theme
shopify theme pull --live

# Or pull a specific theme by ID
shopify theme pull --id <THEME_ID>
```

## Step 4: Local Development

```bash
# Start the development server
shopify theme dev

# This will:
# - Watch for file changes
# - Upload changes to a development theme
# - Provide a preview URL
```

## Step 5: Create Development Store (Optional)

```bash
# Create a development store for testing
shopify store create
```

## Useful Commands

```bash
# View theme information
shopify theme info

# Publish a theme to live
shopify theme publish --id <THEME_ID>

# Create a backup
shopify theme pull --id <THEME_ID> -d backups/backup-$(date +%Y%m%d)

# List all files in a theme
shopify theme list --theme-id <THEME_ID>
```

## Troubleshooting

- If CLI doesn't recognize commands, ensure it's properly installed
- Check your internet connection
- Verify Shopify account has necessary permissions
