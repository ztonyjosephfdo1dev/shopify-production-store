# MCP Servers — Shopify Integration Guide

Version: 1.0
Date: 2026-02-26
Owner: ztonyjosephfdo1dev

---

## Overview

Shopify provides two distinct MCP (Model Context Protocol) servers for different audiences:

| Server | Who It's For | Auth Required | Endpoint |
|---|---|---|---|
| **Dev MCP** | Developer (you) — theme & API development | ❌ None | `npx @shopify/dev-mcp@latest` |
| **Storefront MCP** | Customer-facing — shopping assistant / AI agent | ❌ None | `https://udfphb-uk.myshopify.com/api/mcp` |

---

## 1. Dev MCP Server (`@shopify/dev-mcp`)

### What It Does
Connects your AI coding assistant (VS Code Copilot, Cursor, Claude) directly to Shopify's development resources — docs, API schemas, Liquid validation — so you get accurate Shopify-specific answers while building your theme.

### Tools Available

| Tool | What It Does |
|---|---|
| `learn_shopify_api` | Teaches the AI about Shopify APIs — **call this first** |
| `search_docs_chunks` | Searches across all shopify.dev documentation |
| `fetch_full_docs` | Retrieves full documentation for a specific path |
| `introspect_graphql_schema` | Explores Admin GraphQL API schema (types, queries, mutations) |
| `validate_graphql_codeblocks` | Validates GraphQL code against Shopify schema |
| `validate_component_codeblocks` | Validates Shopify component code (Polaris, etc.) |
| `validate_theme` | Validates entire theme directory with Theme Check |
| `validate_theme_codeblocks` | Validates individual Liquid code snippets |

### Supported APIs
- Admin GraphQL API
- Storefront API
- Customer Account API
- Liquid / Theme
- Functions
- Partner API
- Payment Apps API
- Polaris Web Components
- POS UI Extensions

### Setup — VS Code (GitHub Copilot)

1. Create `.vscode/mcp.json` in your workspace (already created — see file).
2. Restart VS Code.
3. Ask Copilot: *"How do I create a product using the Admin API?"* — it will use the MCP server automatically.

### Setup — Cursor

Add to Cursor Settings → Tools & Integrations → New MCP Server:

```json
{
  "mcpServers": {
    "shopify-dev-mcp": {
      "command": "npx",
      "args": ["-y", "@shopify/dev-mcp@latest"]
    }
  }
}
```

> **Windows alternative** (if connection errors occur):
> ```json
> {
>   "mcpServers": {
>     "shopify-dev-mcp": {
>       "command": "cmd",
>       "args": ["/k", "npx", "-y", "@shopify/dev-mcp@latest"]
>     }
>   }
> }
> ```

### What You Can Ask After Setup
- *"How do I create a product using the Admin API?"*
- *"What fields are available on the Order object?"*
- *"Show me an example of a webhook subscription"*
- *"How do I authenticate my Shopify app?"*
- *"Validate my Liquid template"*
- *"Build a theme section that shows featured products"*

### Requirements
- Node.js 18 or higher
- An AI development tool that supports MCP (VS Code Copilot, Cursor, Claude Code, Gemini CLI)

---

## 2. Storefront MCP Server (Customer-Facing)

### What It Does
Connects an AI shopping assistant directly to **your store's** catalog, cart, and policies. This powers a customer-facing chatbot experience — buyers can search products, ask policy questions, manage their cart, and track orders using natural language.

### Endpoint (No Authentication Needed)
```
POST https://udfphb-uk.myshopify.com/api/mcp
```

### Tools Available

| Tool | What It Does |
|---|---|
| `search_shop_catalog` | Search your store's products by natural language query |
| `search_shop_policies_and_faqs` | Answer questions about return policy, shipping, FAQs |
| `get_cart` | Retrieve current cart contents |
| `add_to_cart` | Add product variants to cart |
| `remove_from_cart` | Remove items from cart |
| `get_order_status` | Track order status for customers |

### Example Request
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 1,
  "params": {
    "name": "search_shop_catalog",
    "arguments": {
      "query": "organic cotton t-shirt",
      "context": "Customer looking for sustainable casual wear"
    }
  }
}
```

### Example Policy Query
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 1,
  "params": {
    "name": "search_shop_policies_and_faqs",
    "arguments": {
      "query": "What is your return policy?",
      "context": "Customer browsing sale items"
    }
  }
}
```

### When to Use Storefront MCP (vs Catalog MCP)
- ✅ You want a chatbot **only** serving your own single store
- ✅ You want product discovery **without** authenticating via Dev Dashboard
- ✅ You want to avoid Catalog MCP rate limits
- ❌ If you need to search **across all Shopify merchants** → use Catalog MCP instead

---

## 3. Catalog MCP (Optional — Global Discovery)

For building AI agents that search across **all Shopify merchants** globally.

| Detail | Value |
|---|---|
| Endpoint | `https://discover.shopifyapps.com/global/mcp` |
| Auth | ✅ Required (JWT token via Dev Dashboard client credentials) |
| Tools | `search_global_products`, `get_global_product_details` |

> This is **not required** for a single-store setup like pookie style. Only needed if you ever want to build a multi-merchant discovery experience.

---

## 4. How They Fit Into This Project

```
Developer (you)
    │
    ├── VS Code / Cursor
    │       └── Dev MCP (@shopify/dev-mcp)
    │               ├── Search Shopify docs
    │               ├── Validate Liquid/GraphQL/Theme
    │               └── Introspect Admin API schema
    │
    └── Production Shopify Store
            └── Storefront MCP (https://your-store.myshopify.com/api/mcp)
                    ├── Customer product search
                    ├── Policy & FAQ answers
                    ├── Cart management
                    └── Order tracking
```

---

## 5. Next Steps

- [ ] Confirm Node.js 18+ is installed: `node --version`
- [ ] `.vscode/mcp.json` is already configured in this workspace (Dev MCP)
- [ ] Update `.vscode/mcp.json` with your real store domain for Storefront MCP
- [ ] Test Dev MCP: Ask Copilot *"Validate my theme using Shopify Theme Check"*
- [ ] Test Storefront MCP: Send a POST request to `https://your-store.myshopify.com/api/mcp`

---

## References
- [Shopify Dev MCP Server](https://shopify.dev/docs/apps/build/devmcp)
- [Storefront MCP Reference](https://shopify.dev/docs/apps/build/storefront-mcp/servers/storefront)
- [Catalog MCP Reference](https://shopify.dev/docs/agents/catalog/mcp)
- [MCP Protocol](https://modelcontextprotocol.io/introduction)
