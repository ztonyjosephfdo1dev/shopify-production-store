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

## AI Product Creation Tool (v2.0)

An admin-only Shopify page with a simple upload form. Backend runs on Google Cloud Functions (permanently free).

### Architecture
```
Shopify Admin Page → Google Cloud Function (Python 3.11) → AI Services → Shopify GraphQL API
```

### Components
- **Frontend:** Shopify Liquid section (`pookie-product-creator.liquid`) — vanilla JS + CSS, no external frameworks
- **Backend:** Google Cloud Function (Python 3.11, HTTP trigger) — serverless, permanently free tier
- **AI Vision + Text:** GPT-4.1-nano — single call: analyzes image + generates name, description, 35-50 tags, SEO, detects category/color/fabric
- **BG Removal:** Photoroom API — removes background, creates white BG + styled AI background (preserves real product)
- **Virtual Try-On:** Replicate VTON (prunaai/p-tryon or omnious/vella-1.5) — maps real garment onto Indian model
- **Shopify Client:** GraphQL Admin API v2026-01 — creates products with images, variants, tags, collection assignment

### Data Flow
1. Staff uploads 1-3 raw phone photos + enters price/sizes (category optional)
2. GPT-4.1-nano analyzes image → generates ALL text + detects garment attributes (one API call)
3. Photoroom removes BG → white background (Image 1) + styled background (Image 2)
4. Replicate VTON → garment on model (Image 3)
5. Raw photo crop → detail/close-up (Image 4)
6. Tool creates Shopify product via GraphQL (status: Draft)

**Cost:** ~₹12/product | Hosting: ₹0/month (GCP free tier — permanent)

See `docs/product-creation-tool.md` for full HLD v2.0 and requirements.

---

## Considerations
- Keep secret keys out of repo.
- Use Shopify development store or duplicate theme for testing before publishing.
- Use branch protections for `main` / `production`.
- MCP servers require Node.js 18+ for Dev MCP. Storefront MCP requires no setup — it is built into Shopify.
- See `docs_mcp-servers.md` for full MCP setup and usage guide.