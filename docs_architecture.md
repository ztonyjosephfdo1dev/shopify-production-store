# Architecture — Shopify Production Store

Version: 1.0  
Date: 2026-02-25  
Owner: ztonyjosephfdo1dev

## Overview
This document describes the logical architecture of the Shopify storefront, the responsibilities of each layer, and integration points.

## Components
- Shopify Store (Production)
  - Theme (Liquid templates, assets, sections, snippets, templates)
  - Store Data (Products, Collections, Customers, Orders)
  - Apps / Integrations (third-party apps, if any)
- Version Control
  - GitHub repository containing theme code and documentation
- Developer Tooling
  - Shopify CLI for theme development and deploys
  - GitHub Actions for optional automated deployments  - **Dev MCP Server** (`@shopify/dev-mcp`): AI assistant access to Shopify docs, API schemas, and Liquid/theme validation during development
- MCP Servers
  - **Dev MCP** (developer-facing): Connects AI coding tools to Shopify documentation and GraphQL schema introspection — no auth required
  - **Storefront MCP** (customer-facing): Built into every Shopify store at `https://{store}.myshopify.com/api/mcp` — powers AI shopping assistants for product search, cart management, and policy queries- Backups & Recovery
  - Git history for code
  - Shopify admin theme versioning
  - Offsite backups (recommended)

## Responsibilities & Boundaries
- Theme code and assets: maintained in GitHub.
- Data (products, orders): resides in Shopify (not in repo).
- Credentials and secrets: stored only in GitHub Secrets or secure vault (do not commit).
- Production changes: restricted to protected branches and controlled deployment process.

## Integration Points
- Shopify Admin: manual theme publish, theme duplication, app management.
- GitHub Actions: optional hook to deploy built/packaged theme to Shopify via Shopify CLI.
- External services (optional): analytics, payment gateways, fulfillment providers.

## Considerations
- Keep secret keys out of repo.
- Use Shopify development store or duplicate theme for testing before publishing.
- Use branch protections for `main` / `production`.
- MCP servers require Node.js 18+ for Dev MCP. Storefront MCP requires no setup — it is built into Shopify.
- See `docs_mcp-servers.md` for full MCP setup and usage guide.