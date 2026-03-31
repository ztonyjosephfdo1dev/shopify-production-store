# Changelog

All notable changes to this project are recorded in this file.

## [1.0] - 2026-02-25
- Initial set of documentation created:
  - requirements.md
  - architecture.md
  - deployment-guide.md
  - deployment-checklist.md
  - backup-guide.md
  - runbook.md
  - discussion-log.md
  - changelog.md

## [1.1] - 2026-03-02
- Deployed mega-menu navigation (9 top-level items, 25 sub-collection links)
- Deployed contact page at /pages/contact
- Resolved 401 token incident — documented client_credentials grant flow
- Created AI Product Creation Tool HLD: `docs/product-creation-tool.md`
  - Full requirements for admin-only tool that generates professional product images from phone photos
  - Architecture: FastAPI + OpenAI (GPT-4V + DALL-E 3) + Shopify GraphQL
  - Covers: image generation pipeline, text generation, preview/review, Shopify product creation
- Updated `docs_architecture.md` with product creation tool system overview

## [1.2] - 2026-03-03
- **CRITICAL FIX:** Complete rewrite of Product Creation Tool HLD (v1.0 → v2.0)
  - Removed DALL-E 3 approach (text-to-image — cannot preserve real garment)
  - New pipeline: Photoroom (BG removal) + Replicate VTON (virtual try-on) + GPT-4.1-nano (text generation)
  - Reduced from 6 images to 4 images per product
  - Changed backend from FastAPI (local) to Google Cloud Functions (serverless, permanently free)
  - Removed password/PIN — admin-only via Shopify page visibility
  - Category now optional — AI auto-detects from image
  - Single GPT-4.1-nano API call generates ALL text: name, description, 35-50 tags, SEO, garment analysis
  - Cost reduced: ~₹12/product (was ~₹32), hosting ₹0/month (GCP permanent free tier)
- Added comprehensive Google Cloud setup guide (Section 7 in HLD)
- Added complete API keys & accounts checklist with sign-up URLs
- Added cost analysis with optimization options
- Verified Shopify scopes: all 44 scopes active, `write_products` + `write_files` confirmed working
- Tested `stagedUploadsCreate` mutation on API v2026-01 — SUCCESS
- Updated `docs_architecture.md` to reflect GCP-based architecture

## [1.3] - 2026-03-10

### 🚀 Major Architecture Upgrade — OpenAI Image Generation (v6)

#### Problem with Previous Architecture (v5 / Replicate VTON)
- idm-vton was discovered to be licensed under **CC BY-NC-SA 4.0 (non-commercial only)** — legal violation on a production e-commerce store
- Bottom wear was inconsistent across images: 2 separate VTON calls used different random model photos → different bottoms in every session
- VTON models cannot generate bottom wear or background — fundamental limitation of try-on architecture
- 3 API calls per product (2× Replicate VTON + 1× OpenAI text) = ~$0.048/product

#### New Architecture — Single OpenAI Image Call
- **Replaced** 2× Replicate VTON calls with **1× OpenAI GPT Image API call**
- OpenAI generates a **2×3 grid of 6 model poses** in a single image (consistent model, consistent bottom wear, consistent background across all 6 panels)
- PIL (local) crops the grid into: **hero image** (front view, panel 1) + **6-panel lookbook collage**
- Zero extra API cost for collage assembly
- **Cost: ~$0.016/product** (down from ~$0.048) — 67% reduction

#### Adapter Pattern Introduced
- New file: `services/image_provider.py`
- `ImageProvider` abstract base class with `generate_pose_grid()` interface
- `OpenAIImageProvider` — primary provider (gpt-image-1-mini, Responses API, `input_fidelity: high`)
- `FashnAIProvider` stub — ready to plug in FASHN.ai ($0.075/image) if quality upgrade needed
- `ReplicateVTONProvider` stub — legacy, kept for testing/comparison only
- Provider selected via `IMAGE_PROVIDER` env var (default: `openai`)
- Model selected via `IMAGE_MODEL` env var (default: `gpt-image-1-mini`)

#### New OpenAI Text Fields
Added 3 new fields to `openai_service.py` JSON schema:
- `target_persona` — `"genz"` or `"professional"` (AI decides from garment)
- `model_prompt` — rich scene description passed to image generator (model type, bottom wear, accessories, background, photography style)
- `styling_tip` — one-liner "Complete the Look" appended to product description

#### Image Utility Redesign (`image_utils.py` → v6)
- `crop_pose_grid()` — splits 2×3 AI grid into 6 individual JPEG panels
- `build_collage_from_grid()` — returns `{hero, collage, panels}` dict
- `_assemble_collage_from_panels()` — builds 2×3 collage canvas (968×1936px)
- `_resize_cover()` — cover-mode resize with center crop
- Legacy `build_smart_collage()` preserved for backward compatibility
- Constants renamed: `PANEL_W/H/GAP/BG_COLOR` → `COLLAGE_PANEL_W/H/GAP/BG`

#### Quality Dropdown Added to UI
- New "Image Quality" field in upload form (before submit button)
- Options: Low (~₹1), **Medium — default** (~₹4), High (~₹17)
- `image_quality` appended to FormData and passed to backend
- Backend default (if field missing): `"low"` — safe cost fallback
- UI default (selected): `"medium"` — good quality for production use

#### Shopify GraphQL Fix
- `productCategory` field removed from `productCreate` mutation — field was removed in Shopify Admin API v2026-01, causing `userErrors` on every product creation
- Category is now set via a separate `productUpdate` call immediately after product creation (best-effort, non-blocking)

#### UI Updates
- Progress animation text updated to reflect new pipeline ("Creating 6-pose model lookbook grid..." etc.)
- AI generation failure warning updated: removed Replicate billing link, now points to OpenAI API key
- AI Analysis preview section now shows `target_persona` and `styling_tip`
- Styling tip rendered in product description as: `✨ Complete the Look: {tip}`

#### Files Changed
| File | Change |
|---|---|
| `services/image_provider.py` | **NEW** — full adapter system |
| `services/openai_service.py` | +3 new JSON fields |
| `services/image_utils.py` | v5 → v6, new grid functions |
| `main.py` | v5 → v6, new pipeline wired |
| `services/shopify_service.py` | productCategory fix |
| `theme/sections/pookie-product-creator.liquid` | quality dropdown + progress text |
| `deploy_script.py` | image_provider.py added to DEPLOY_FILES |

#### Deployed
- Cloud Function: `create-product` (GCP `asia-south1`, Python 3.12, 512MB, 300s)
- Theme: `135917666402` (pookiestyle.in)
- Date: 2026-03-10

---

Notes:
- Update this file for every production deployment or major change.