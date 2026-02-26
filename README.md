# shopify-production-store

Repository intended to store Shopify theme code and project documentation for the production Shopify store owned by `ztonyjosephfdo1dev`.

## Purpose
- Keep theme code versioned
- Host project docs (docs/)
- Provide deployment and recovery runbooks

## Structure
See `docs/requirements.md` and `docs/architecture.md` for full details.

## Getting Started
1. Clone repo
2. Install Shopify CLI
3. Configure `shopify.theme.toml` with production store details (only after creating backups and duplicates)
4. Use `docs/deployment-guide.md` before any push to production.

## MCP Servers
This project uses two Shopify MCP (Model Context Protocol) servers:

| Server | Purpose | Auth |
|---|---|---|
| **Dev MCP** (`@shopify/dev-mcp`) | AI-assisted theme development — Shopify docs, schema, Liquid validation | None |
| **Storefront MCP** (`{store}.myshopify.com/api/mcp`) | Customer-facing AI shopping assistant — product search, cart, policies | None |

- VS Code is pre-configured via `.vscode/mcp.json` — Storefront MCP is connected to `udfphb-uk.myshopify.com`.
- See [docs_mcp-servers.md](docs_mcp-servers.md) for full setup instructions.

## Testing
> **Note:** Automated test cases are not used in this project and are intentionally excluded from the workflow. Validation is handled via manual preview on a duplicate Shopify theme before publishing to production.

## Contact
Owner: `ztonyjosephfdo1dev`