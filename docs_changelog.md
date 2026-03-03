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

Notes:
- Update this file for every production deployment or major change.