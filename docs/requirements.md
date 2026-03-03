# Shopify Production Store Setup

## Action Items & Status

| # | Action Item | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Create a GitHub repository (e.g., shopify-production-store) | ztonyjosephfdo1dev | 🔴 High | ✅ Completed |
| 2 | Initialize the repository with the recommended folder structure | ztonyjosephfdo1dev | 🔴 High | ✅ Completed |
| 3 | Connect Shopify store to GitHub using Shopify CLI | ztonyjosephfdo1dev | 🔴 High | 🔲 Pending |
| 4 | Store this document as docs/requirements.md in the repo | ztonyjosephfdo1dev | 🟡 Medium | ✅ Completed |
| 5 | Set up GitHub Actions for automated deployment (optional) | ztonyjosephfdo1dev | 🟡 Medium | 🔲 Pending |
| 6 | Create a Shopify development store for safe testing | ztonyjosephfdo1dev | 🟡 Medium | 🔲 Recommended |
| 7 | Establish backup strategy for production theme | ztonyjosephfdo1dev | 🔴 High | 🔲 Pending |

## Folder Structure

```
shopify-production-store/
├── .github/
│   ├── workflows/
│   │   └── deploy.yml          # GitHub Actions deployment workflow
│   └── CODEOWNERS
├── theme/                       # Shopify theme files
│   ├── assets/
│   ├── config/
│   ├── layout/
│   ├── locales/
│   ├── sections/
│   ├── snippets/
│   ├── templates/
│   └── theme.json
├── backups/                     # Theme backups
│   └── .gitkeep
├── docs/
│   ├── requirements.md          # This file
│   ├── setup-guide.md
│   ├── deployment.md
│   └── backup-strategy.md
├── scripts/
│   ├── backup.sh                # Backup automation scripts
│   └── deploy.sh
├── .shopifyrc                   # Shopify CLI configuration (add to .gitignore)
├── .gitignore
├── README.md
└── package.json                 # Node dependencies for theme development
```

## Next Steps

1. **Install Shopify CLI**: Download from [Shopify CLI](https://shopify.dev/docs/themes/tools/cli)
2. **Authenticate with Shopify**: `shopify auth login`
3. **Link your store**: `shopify theme pull --live` (to download current theme)
4. **Set up Git workflow**: Configure branch protection and review policies
5. **Create development store**: For testing before production deployment
6. **Implement backup strategy**: Automated theme backups before deployments

## Notes
- Keep sensitive credentials in `.env` files (add to `.gitignore`)
- Use semantic versioning for theme releases
- Always test in development/staging store first
- Maintain theme backups before major changes
