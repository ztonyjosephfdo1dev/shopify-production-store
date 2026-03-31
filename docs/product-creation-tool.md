# AI-Powered Product Creation Tool — HLD & Requirements

Version: 3.0  
Date: 2026-03-10  
Author / Stakeholder: ztonyjosephfdo1dev  
Store: Pookie Style (`udfphb-uk.myshopify.com` | `pookiestyle.in`)

---

## 1. Executive Summary

A **Shopify admin-only page** with a simple upload form. Staff uploads 1-3 raw phone photos + enters price, sizes, quality level. **Two API calls** do everything:

1. **GPT-4o-mini** (text) — analyzes garment → product name, description, 35-50 tags, SEO, `model_prompt`, `styling_tip`, `target_persona`
2. **gpt-image-1-mini** (image) — generates a 2×3 grid of **6 model poses in a single image** (consistent model, bottom wear, background across all 6 panels)
3. **PIL** (local, free) — crops grid into hero image (front view, panel 1) + 6-panel lookbook collage

**Goal:** Any staff member uploads a phone photo → product fully listed on Shopify in 30–90 seconds.

**Cost: ~$0.016 (~₹1.3) per product at medium quality. Hosting: ₹0/month (GCP free tier — permanent).**

---

## 2. Problem Statement

Listing a product manually takes 20-30 minutes: photography, writing, tagging, variant setup, collection assignment. This tool reduces it to a 30-second form fill + 30–90 second automated processing.

### Why We Moved Away from VTON (Replicate)

| Issue | Detail |
|---|---|
| **Non-commercial license** | idm-vton is CC BY-NC-SA 4.0 — illegal to use in a for-profit store |
| **Inconsistent bottom wear** | 2 separate VTON calls pulled 2 random model photos → different bottoms in each image every session |
| **Cannot generate bottoms** | VTON models only replace the garment zone — cannot generate what the model wears below |
| **Higher cost** | 2× Replicate calls = ~$0.048/product vs $0.016 now |

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Shopify Admin Page                            │
│   pookie-product-creator.liquid  (Liquid + Vanilla JS, no framework) │
│                                                                      │
│   Upload form: 1-3 photos + price + sizes + quality dropdown         │
│   Two-step flow: Preview screen → review/edit → Confirm → Created    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  POST multipart/form-data
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Google Cloud Function (Python 3.12)                     │
│   create_product_handler — asia-south1 — 512MB — 300s timeout        │
│                                                                      │
│  ┌─────────────────────┐   ┌────────────────────────────────────┐    │
│  │  openai_service.py  │   │        image_provider.py           │    │
│  │  (gpt-4o-mini text) │   │   (adapter — IMAGE_PROVIDER env)   │    │
│  │                     │   │                                    │    │
│  │  → product_name     │   │  OpenAIImageProvider  (default)    │    │
│  │  → description      │   │  gpt-image-1-mini                  │    │
│  │  → 35-50 tags       │   │  Responses API + image_generation  │    │
│  │  → seo_title        │   │  1024×1536, input_fidelity=high    │    │
│  │  → model_prompt ────┼───┼──► single 2×3 grid image           │    │
│  │  → styling_tip      │   │                                    │    │
│  │  → target_persona   │   │  FashnAIProvider  (stub, future)   │    │
│  └──────────┬──────────┘   │  ReplicateVTONProvider  (legacy)   │    │
│             │              └──────────────┬─────────────────────┘    │
│             │                             │  grid_bytes              │
│             │                             ▼                          │
│             │              ┌────────────────────────────────────┐    │
│             │              │        image_utils.py (PIL)        │    │
│             │              │  crop_pose_grid() → 6 panels       │    │
│             │              │  build_collage_from_grid()         │    │
│             │              │  → hero  (panel 1, front view)     │    │
│             │              │  → collage  (2×3, 968×1936px)      │    │
│             │              └──────────────┬─────────────────────┘    │
│             │                             │                          │
│             └──────────────┬──────────────┘                         │
│                            │ preview JSON (base64 images + all text) │
└────────────────────────────┼─────────────────────────────────────────┘
                             │  Step 1: return preview → staff reviews
                             ▼
                  Staff reviews, edits name/description/status, confirms
                             │  Step 2: confirm (JSON)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│            shopify_service.py  (same Cloud Function)                 │
│                                                                      │
│  1. stagedUploadsCreate  → upload hero + collage to Shopify CDN      │
│  2. productCreate        → title, desc, tags, SEO, media, options    │
│  3. productVariantsBulkCreate → S/M/L/XL/XXL + price                │
│  4. inventorySetQuantities    → stock per variant × location         │
│  5. collectionAddProducts     → auto-assign collections              │
│  6. productUpdate             → set taxonomy category (v2026-01 fix) │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow (Step by Step)

### Step 1 — Preview (`?action=preview`)

1. Staff submits form: 1-3 photos + price + sizes + quality + optional fields
2. **Text analysis** (1 OpenAI call, ~$0.0003):
   - gpt-4o-mini analyzes garment photo(s)
   - Returns structured JSON: `product_name`, `description`, `tags`, `seo_title`, `seo_description`, `detected_garment_type`, `dress_style`, `target_persona`, `model_prompt`, `styling_tip`, `garment_brief`, `accessories_note`, `suggested_collections`, `detected_color`, `detected_fabric`, `detected_style`, `detected_occasion`
3. **Image generation** (1 OpenAI call, ~$0.006–$0.052 depending on quality):
   - `image_provider.generate_pose_grid(garment_bytes, model_prompt, quality, extra_prompt)`
   - OpenAI Responses API generates a single 1024×1536 image containing a 2×3 grid of 6 poses
   - Same model, same bottom wear, same background across all 6 panels — fully consistent
4. **Grid processing** (PIL, local, $0.00):
   - `build_collage_from_grid(grid_bytes)` → `{hero, collage, panels}`
   - Hero = panel 1 (front view) → becomes Shopify product photo 1
   - Collage = 2×3 reassembly of all 6 panels (968×1936px) → Shopify product photo 2
5. **Preview JSON** returned to browser — no Shopify product created yet

### Step 2 — Confirm (`?action=confirm`)

1. Browser sends confirmed payload: final name, description, base64 hero + collage, status, quantity
2. Upload both images to Shopify via `stagedUploadsCreate` (PUT to GCS signed URL)
3. `productCreate` — title, description, tags, SEO, vendor, product type, media
4. `productVariantsBulkCreate` — one variant per size with price + compare-at
5. `inventorySetQuantities` — set stock level per variant at default location
6. `collectionAddProducts` — assign to resolved collection handles
7. `productUpdate` — set taxonomy category node (moved out of productCreate for v2026-01 API)
8. Return product URL + admin URL to browser

---

## 5. Functional Requirements

### 5.1 Inputs (Staff Provides)

| Field | Required | Default | Notes |
|---|---|---|---|
| **Photos** | Yes | — | 1-3 images (phone, hanger, flat-lay, mannequin). Max 10MB each |
| **Selling price (₹)** | Yes | — | MRP |
| **Compare-at price (₹)** | Yes | — | Strikethrough price |
| **Sizes** | Yes | — | S, M, L, XL, XXL, Free Size checkboxes |
| **Image Quality** | Yes | Medium | Low/Medium/High dropdown |
| **Category** | No | AI detects | Auto-assigns to collection if provided |
| **Product name** | No | AI generates | AI uses if blank |
| **Description/notes** | No | AI generates | Option to use as-is (skip rewrite) |
| **Styling/pose instructions** | No | — | Appended to image generation prompt |
| **Inventory quantity** | No | 1 | Per size variant |
| **Product status** | No | Draft | Draft or Active |

### 5.2 AI Text Fields (Output of Single GPT Call)

| Field | Description |
|---|---|
| `product_name` | SEO-friendly (e.g., "Emerald Embroidered A-Line Kurti") |
| `description` | 3-5 sentence HTML, brand voice: trendy, feminine, relatable |
| `tags` | 35-50 tags: garment type, color, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, search keywords |
| `seo_title` | ≤70 chars, Google-optimized |
| `seo_description` | ≤160 chars meta description |
| `detected_garment_type` | kurti, crop-top, dress, gown, cord-set, etc. |
| `detected_color` | Primary color |
| `detected_fabric` | Cotton, silk, georgette, etc. |
| `detected_style` | Casual, ethnic, western, party, etc. |
| `detected_occasion` | Daily-wear, party, wedding, festival, etc. |
| `dress_style` | `western` or `ethnic` |
| `garment_brief` | Short description for image generation |
| `accessories_note` | Suggested accessories |
| `target_persona` | `genz` or `professional` (AI decides from garment) |
| `model_prompt` | Rich scene description for image generator: model type + bottom wear + accessories + background + photography style |
| `styling_tip` | One-liner "Complete the Look" tip appended to product description as `✨ Complete the Look: ...` |
| `suggested_collections` | Array of Shopify collection handles for auto-assignment |

### 5.3 AI Image Output (6-Pose Grid)

Single OpenAI call → 1024×1536px image containing 2×3 grid:

| Panel | Position | Pose | Usage |
|---|---|---|---|
| 1 | Row 1, Left | Front full-body, hands at sides | **Hero image** (Shopify photo 1) |
| 2 | Row 1, Right | Back full-body | Collage |
| 3 | Row 2, Left | 3/4 angle from right | Collage |
| 4 | Row 2, Right | Upper-body close-up (neckline, sleeve, fabric) | Collage |
| 5 | Row 3, Left | Walking pose, natural stride | Collage |
| 6 | Row 3, Right | Side pose, one hand on hip | Collage |

PIL crops grid into 6 individual panels → hero (panel 1) + 6-panel collage (968×1936px).

### 5.4 Shopify Product Result

- Title, description (with styling tip), vendor ("Pookie Style"), product type, tags, SEO
- Status: Draft (default) or Active
- 2 images: hero (front view) + 6-panel lookbook collage
- Size variants with price + compare-at price
- Inventory per variant at default location
- Collection auto-assignment
- Taxonomy category (best-effort via `productUpdate`)

---

## 6. Cost Analysis

### Per-Product Cost

| Step | Service | Low (~₹0.5) | Medium (~₹1.3) | High (~₹4.3) |
|---|---|---|---|---|
| Text analysis | gpt-4o-mini | $0.0003 | $0.0003 | $0.0003 |
| Image generation | gpt-image-1-mini | $0.006 | $0.015 | $0.052 |
| Grid crop + collage | PIL (local) | $0.00 | $0.00 | $0.00 |
| **Total** | **2 API calls** | **~$0.006** | **~$0.016** | **~$0.052** |

### Quality Upgrade Path

| Model | Low | Medium | High | Switch |
|---|---|---|---|---|
| gpt-image-1-mini (current) | $0.006 | $0.015 | $0.052 | Default |
| gpt-image-1.5 | $0.013 | $0.050 | $0.200 | Set `IMAGE_MODEL=gpt-image-1.5` in `.env.yaml` |

### Monthly Cost Estimate (Medium Quality)

| Volume | Cost |
|---|---|
| 50 products/mo | ~₹65 |
| 200 products/mo | ~₹260 |
| 500 products/mo | ~₹650 |
| **Hosting** | **₹0 (GCP free tier — permanent)** |

---

## 7. Provider Adapter System

`services/image_provider.py` — swap image generation provider via env var, no code change.

### Configuration (`.env.yaml`)

```yaml
IMAGE_PROVIDER: openai          # openai | fashn | replicate
IMAGE_MODEL: gpt-image-1-mini   # or gpt-image-1.5 for quality upgrade
```

### Providers

| Provider | `IMAGE_PROVIDER` | Status | Cost/image | Notes |
|---|---|---|---|---|
| OpenAI gpt-image-1-mini | `openai` | ✅ Active | $0.006–$0.052 | Current default |
| OpenAI gpt-image-1.5 | `openai` + `IMAGE_MODEL=gpt-image-1.5` | ✅ Ready | $0.013–$0.200 | Best quality |
| FASHN.ai | `fashn` | 🔧 Stub (future) | $0.049–$0.075 | Purpose-built for fashion |
| Replicate VTON | `replicate` | ⚠️ Deprecated | ~$0.020 | Non-commercial license only |

---

## 8. File Structure

```
product-tool/
├── main.py                      # Cloud Function entry — preview + confirm
├── requirements.txt             # Python deps (functions-framework, openai, httpx, Pillow)
├── deploy_script.py             # GCP deploy automation
├── push_theme.py                # Shopify theme push automation
├── .env.yaml                    # Secrets (gitignored)
└── services/
    ├── __init__.py
    ├── image_provider.py        # ★ Adapter: OpenAI / FASHN / Replicate
    ├── image_utils.py           # PIL grid crop + collage assembly (v6)
    ├── openai_service.py        # Text analysis — gpt-4o-mini cascade
    ├── shopify_service.py       # Shopify GraphQL — upload, create, assign
    └── replicate_service.py     # Legacy VTON (deprecated, not imported)

theme/
└── sections/
    └── pookie-product-creator.liquid  # Frontend — upload form + preview + confirm
```

---

## 9. Environment Variables (`.env.yaml`)

| Variable | Purpose | Example |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `SHOPIFY_STORE` | Store domain | `udfphb-uk.myshopify.com` |
| `SHOPIFY_ACCESS_TOKEN` | Admin API token (auto-refreshed on 401) | `shpat_...` |
| `SHOPIFY_CLIENT_ID` | OAuth app client ID (for auto-refresh) | `14a5...` |
| `SHOPIFY_CLIENT_SECRET` | OAuth app client secret | `shpss_...` |
| `IMAGE_PROVIDER` | Provider: `openai` \| `fashn` \| `replicate` | `openai` |
| `IMAGE_MODEL` | Image model name | `gpt-image-1-mini` |

---

## 10. Deployment

### Cloud Function

```powershell
cd product-tool
python deploy_script.py
```

Copies required files to `C:\tmp\pookie-deploy` (no-space path) → `gcloud functions deploy`.

### Theme

```powershell
cd product-tool
python push_theme.py
```

Pushes `pookie-product-creator.liquid` to theme `135917666402`.

### Post-Deploy Verification

```powershell
# Expect HTTP 400 "No images uploaded" — confirms function is live and routing
curl.exe -X POST https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product?action=preview -d "{}"
```

---

## 11. Shopify GraphQL API Notes (v2026-01)

| Change | Fix Applied |
|---|---|
| `productCategory` removed from `ProductCreateInput` | Now set via separate `productUpdate` after creation |
| Variants removed from `ProductCreateInput` | Uses `productVariantsBulkCreate` separately (since v2024-01) |
| Inventory via `inventorySetQuantities` | Uses `InventorySetQuantitiesInput` with `name: "available"` |

---

## 12. Security

- All secrets in `.env.yaml` (gitignored) — never in source code
- Shopify token auto-refreshes on 401 via Client Credentials Grant — zero manual intervention needed
- No stack traces in API responses — only human-readable errors
- All external API calls have explicit timeouts (`httpx timeout=30.0`)
- See `docs_security.md` for full security standards and incident log

---

## 13. User Flow (Current)

```
Staff opens: pookiestyle.in/pages/product-upload
(Must be logged into Shopify Admin — page is unlisted/hidden from storefront)

  [Drag & drop photos]
  Price: ₹599    Compare: ₹999
  Sizes: ✓S  ✓M  ✓L  ✓XL
  Category: (optional — AI detects)
  Description: (optional)
  Image Quality: ○ Low  ● Medium  ○ High

  [Generate Preview]

  ████████████░░░░░  70%
  "Creating 6-pose model lookbook grid..."

  ─── Preview Screen ───────────────────
  [Hero — Front View]   [6-Pose Collage]

  Product Name:  [editable text field]
  Description:   [AI Generated | My Description toggle]
  Tags: kurti  embroidered  green  cotton  ...
  AI Analysis: Type: kurti  Persona: genz  Tip: Pair with palazzo...

  Status: [Draft ▼]   Inventory: [1 per variant]

  [← Back to Edit]   [Create Product on Shopify →]

  ─── Success ────────────────────────────
  ✅ Product Created Successfully!
  "Emerald Embroidered A-Line Kurti"
  [View in Shopify Admin →]   [View on Store →]
  [Create Another Product]
```

---

## 14. Version History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-03-02 | Initial HLD — FastAPI + DALL-E 3 approach |
| 2.0 | 2026-03-03 | Rewrite — GCP + Replicate VTON + Photoroom + GPT-4.1-nano |
| **3.0** | **2026-03-10** | **Current — OpenAI single image call, 6-pose 2×3 grid, adapter pattern, quality dropdown, productCategory fix** |

---

## Document Control

- Version: 3.0
- Date: 2026-03-10
- Author: ztonyjosephfdo1dev
- Status: **Implemented and deployed to production**

