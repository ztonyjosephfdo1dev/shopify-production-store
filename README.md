# Shopify Production Store

This repository contains the theme and configuration for the Shopify production store, with version control, automated deployment, and backup management.

## Features

- 📦 Theme management with Shopify CLI
- 🚀 Automated deployment via GitHub Actions
- 💾 Automated backup strategy
- 📝 Version control for all theme files
- 🔄 Development/staging workflow

## Quick Start

### Prerequisites
- [Shopify CLI](https://shopify.dev/docs/themes/tools/cli)
- [Node.js](https://nodejs.org/) 14+
- Git

### Installation

```bash
# Install dependencies
npm install

# Authenticate with Shopify
shopify auth login

# Pull the current live theme
shopify theme pull --live

# Start development
shopify theme dev
```

## Folder Structure

See [docs/requirements.md](docs/requirements.md) for detailed folder structure and action items.

## Deployment

See [docs/deployment.md](docs/deployment.md) for deployment instructions.

## Backup & Recovery

See [docs/backup-strategy.md](docs/backup-strategy.md) for backup procedures.

## Documentation

- [Setup Guide](docs/setup-guide.md)
- [Deployment Guide](docs/deployment.md)
- [Backup Strategy](docs/backup-strategy.md)
- [Requirements & Action Items](docs/requirements.md)

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Test in development store
4. Submit pull request for review
5. After approval, merge to `main` for deployment

## Support

For questions or issues, contact the project owner.
