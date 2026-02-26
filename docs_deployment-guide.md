# Deployment Guide — Shopify Production Store

Version: 1.0  
Date: 2026-02-25  
Owner: ztonyjosephfdo1dev

## Purpose
Procedures for preparing, testing, and deploying Shopify theme changes to the production store.

## Prerequisites
- GitHub repository initialized and pushed.
- Shopify CLI installed and authenticated.
- Access to Shopify Admin account for the production store.
- Backup of existing live theme (duplicate theme in Shopify Admin).
- (Optional) GitHub Actions secrets configured for automated deploys.

## Deployment Types
- Manual (recommended for single stakeholder)
- Automated (GitHub Actions on merge to `main` or `production`)

---

## Manual Deployment Steps (Shopify CLI)
1. Duplicate live theme in Shopify Admin as a backup.
2. Clone repository locally:
   - git clone <repo-url>
3. Install dependencies (if using build process, e.g., Node tooling):
   - npm install
4. Build assets (if applicable):
   - npm run build
5. Authenticate Shopify CLI (if not already):
   - shopify login --store your-store.myshopify.com
6. Connect theme (or update shopify.theme.toml with production theme id):
   - shopify theme pull --theme <backup-theme-id> (to pull current)
7. Preview locally (optional):
   - shopify theme serve
8. Push theme to Shopify (to a duplicate theme first):
   - shopify theme push --theme <duplicate-theme-id> --env=production
9. Review theme in Shopify preview. Validate site functionality.
10. When satisfied, publish the duplicate theme from Shopify Admin.

---

## Automated Deployment (GitHub Actions) — High level
- Create workflow that runs on push/merge to `production` branch.
- Workflow checks out code, installs dependencies, builds assets, authenticates with Shopify using secrets, and runs `shopify theme push`.
- Ensure secrets: SHOPIFY_STORE, SHOPIFY_PASSWORD (or API key), SHOPIFY_THEME_ID

---

## Post-deployment
- Smoke test key user journeys (homepage, product page, cart, checkout flow).
- Monitor logs and recent orders for anomalies.
- If problems are found, follow rollback flow.

---

## Rollback Flow
1. Revert commit(s) in GitHub or checkout previous tag/commit locally.
2. Push reverted code to repository and deploy to duplicate theme.
3. Test preview. If OK, publish duplicate theme.
4. If urgent, publish previous known-good theme copy directly from Shopify Admin (if available).

---

## Notes
- Avoid editing production theme directly in Shopify admin when using Git workflow.
- Always create a theme duplicate before publishing changes.