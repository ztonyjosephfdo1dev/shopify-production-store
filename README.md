# Pookie Style — Automation & Theme

AI-powered Shopify store automation for **pookiestyle.in**. Includes the custom theme, a Google Cloud Function backend that turns a phone photo into a fully-listed Shopify product in ~2 minutes, and all deployment tooling.

---

## What's Inside

| Folder / File | Purpose |
|---|---|
| `theme/` | Shopify Liquid theme (sections, templates, assets) |
| `product-tool/` | Python backend — Cloud Function that creates products |
| `scripts/` | Backup and utility shell scripts |
| `docs/` | Technical documentation |
| `deploy_script.py` | One-command GCP Cloud Function deploy |
| `push_theme.py` | One-command Shopify theme push |

---

## AI Product Creation Tool

A staff member uploads 1–3 product photos + price + sizes. The tool:

1. Sends the photo to **OpenAI gpt-image-1-mini** → generates a 2×3 grid of 6 styled poses
2. Crops the grid into 6 individual panels using **PIL** (zero extra API cost)
3. Assembles a hero image + a collage of all poses
4. Calls **OpenAI gpt-4.1-nano** → generates product name, description, 35–50 tags, SEO fields, target persona, styling tip
5. Creates the product on Shopify via **GraphQL Admin API** with all images, variants, and metadata

**Result:** ~2-minute automated workflow. ~₹1.30 per product (low quality) to ~₹4.30 (high quality).

---

## Quick Start — Deploy the Cloud Function

### Prerequisites
- Python 3.12+
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) — authenticated (`gcloud auth login`)
- API keys: `OPENAI_API_KEY`, `SHOPIFY_ACCESS_TOKEN`

### Deploy backend to GCP
```bash
cd product-tool
python ../deploy_script.py
```
Deploys to: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product`

### Push theme changes to Shopify
```bash
python push_theme.py
```
Pushes to theme ID `135917666402` on `udfphb-uk.myshopify.com`.

### Environment Variables (set in GCP or `.env`)
| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (`sk-...`) |
| `SHOPIFY_STORE` | `udfphb-uk.myshopify.com` |
| `SHOPIFY_ACCESS_TOKEN` | `shpat_...` |
| `IMAGE_PROVIDER` | `openai` (default) \| `fashn` \| `replicate` |
| `IMAGE_MODEL` | `gpt-image-1-mini` (default) |

---

## Cost Reference

| Quality | Cost per product | Use when |
|---|---|---|
| Low | ~₹1.30 | Testing, drafts |
| Medium | ~₹3.20 | Standard listings |
| High | ~₹4.30 | Hero products, featured items |

Google Cloud hosting: **₹0/month** (always-free tier — 2M invocations/month).

---

## Folder Structure

```
theme/                        Shopify Liquid theme
  sections/
    pookie-product-creator.liquid   AI product creation form (UI)
  assets/
    pookie-product-creator.css
  templates/
    page.product-upload.json        Page template for the tool

product-tool/                 GCP Cloud Function backend
  main.py                     Entry point: create_product_handler()
  deploy_script.py            Deploys to GCP Cloud Functions
  services/
    image_provider.py         Provider adapter (OpenAI / FASHN / Replicate)
    image_utils.py            PIL grid crop + collage assembly
    openai_service.py         Text generation (name, desc, tags, SEO)
    shopify_service.py        GraphQL product creation

docs/
  product-creation-tool.md    Full technical spec (v3.0)
  setup-guide.md              Initial GCP + API key setup
```

---

## Documentation

| Doc | What's in it |
|---|---|
| [docs/product-creation-tool.md](docs/product-creation-tool.md) | Full technical spec — architecture, pipeline, cost breakdown |
| [docs_architecture.md](docs_architecture.md) | System-wide architecture diagram |
| [docs_changelog.md](docs_changelog.md) | Version history and change log |
| [docs_runbook.md](docs_runbook.md) | Incident response and routine ops |
| [docs_deployment-guide.md](docs_deployment-guide.md) | Step-by-step deployment |
| [docs_security.md](docs_security.md) | API key management, access control |
| [docs/setup-guide.md](docs/setup-guide.md) | First-time GCP + API key setup |

---

## Support

Owner: `ztonyjosephfdo1dev`  
Store: [pookiestyle.in](https://pookiestyle.in)  
GCP Project: `pookie-style-automation` (region: `asia-south1`)
