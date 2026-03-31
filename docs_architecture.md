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

## AI Product Creation Tool (v6 — current)

An admin-only Shopify page with a simple upload form. Backend runs on Google Cloud Functions (permanently free).

### Architecture
```
Shopify Admin Page → Google Cloud Function (Python 3.12) → OpenAI APIs → PIL (local) → Shopify GraphQL API
```

### Components
- **Frontend:** `pookie-product-creator.liquid` — vanilla JS + CSS, no frameworks. Quality dropdown (low/medium/high), drag-drop upload, two-step preview/confirm flow
- **Backend:** Google Cloud Function (Python 3.12, HTTP trigger, 512MB, 300s timeout, `asia-south1`)
- **AI Text:** gpt-4o-mini → gpt-4.1-nano → gpt-3.5-turbo (cascade fallback) — generates name, description, 35-50 tags, SEO, `model_prompt`, `styling_tip`, `target_persona`
- **AI Image:** gpt-image-1-mini (OpenAI Responses API) — generates a single 1024×1536 image containing a **2×3 grid of 6 model poses** in one API call. Model and bottom wear are consistent across all 6 panels
- **Image Processing:** PIL (local, zero cost) — crops 2×3 grid into hero (panel 1, front view) + 6-panel lookbook collage
- **Provider Adapter:** `image_provider.py` — `IMAGE_PROVIDER` env var selects `openai` (default) | `fashn` (stub) | `replicate` (legacy stub)
- **Shopify Client:** GraphQL Admin API v2026-01 — staged uploads, product creation, variant creation, inventory, collection assignment

### Data Flow
1. Staff uploads 1-3 raw phone photos + enters price, sizes, quality (optional: category, description, styling notes)
2. **Step 1 — Text** (1 OpenAI call ~$0.0003): GPT analyzes garment → generates ALL text + `model_prompt` (scene description for image generation) + `styling_tip` + `target_persona`
3. **Step 2 — Image** (1 OpenAI call ~$0.015 medium): gpt-image-1-mini generates 6-pose grid — same model, same bottom wear, same background across all poses
4. **Step 3 — Crop** (local PIL, $0.00): grid cropped into hero + 6-panel collage
5. **Preview returned** to browser (2 images + all text, not yet on Shopify)
6. Staff reviews, edits name/description/status, clicks Confirm
7. **Confirm** — images uploaded to Shopify staged storage → product created → variants → inventory → collection assignment

### Cost Per Product
| Step | Service | Cost |
|---|---|---|
| Text analysis | gpt-4o-mini | ~$0.0003 |
| Image generation (medium) | gpt-image-1-mini | ~$0.015 |
| Grid crop + collage | PIL local | $0.00 |
| **Total** | **2 API calls** | **~$0.016 (~₹1.3)** |

### Provider Adapter — Future Swap
- `IMAGE_PROVIDER=fashn` → switches to FASHN.ai ($0.075/image, purpose-built fashion)
- `IMAGE_PROVIDER=openai` → current default
- `IMAGE_MODEL=gpt-image-1.5` → upgrade to higher quality model (no code change)

See `docs/product-creation-tool.md` for full HLD v3.0 and requirements.

---

## Considerations
- Keep secret keys out of repo.
- Use Shopify development store or duplicate theme for testing before publishing.
- Use branch protections for `main` / `production`.
- MCP servers require Node.js 18+ for Dev MCP. Storefront MCP requires no setup — it is built into Shopify.
- See `docs_mcp-servers.md` for full MCP setup and usage guide.