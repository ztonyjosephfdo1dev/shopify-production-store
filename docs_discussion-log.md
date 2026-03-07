# Discussion Log

This file captures the discussion history and decisions made between the stakeholder and Copilot assistant.

- 2026-02-24 — Initial request: Create a comprehensive document capturing requirements and discussion for Shopify production store.
  - Decision: Single document created as `requirements.md`.
  - Stakeholder: `ztonyjosephfdo1dev`

- 2026-02-24 — Request: Provide `requirements.md` contents for copying.
  - Action: Provided `requirements.md` content formatted for direct copy.

- 2026-02-25 — Request: Provide all other files, flows, and discussions as separate files.
  - Action: Created these supporting docs: architecture, deployment guide, runbook, backup guide, deployment checklist, discussion log, and CI/templates.

- 2026-03-02 — **INCIDENT: Both API tokens returned 401 Unauthorized**
  - Affected tokens: `shpat_***REDACTED***` and `shptka_***REDACTED***`
  - Root cause: App at `dev.shopify.com` released a new version (`all_orders_access`), which invalidated the previous access token.
  - Failed approaches tried: OAuth redirect URL flow (got `redirect_uri not whitelisted`), Admin custom app checkboxes (not available for Partners app), creating a new app from Admin.
  - **RESOLUTION: Client Credentials Grant Flow** — Partners Dashboard apps support token generation using just Client ID + Secret with `grant_type=client_credentials`. No OAuth redirect needed.
  - New working token generated: `shpat_***REDACTED***`
  - Header updated to mega-menu mode on live Rise theme (ID: 135917666402).
  - See `docs_security.md` for the exact PowerShell command to regenerate the token.

- 2026-03-02 — **DECISION: Finalized Navigation Menu Structure (mega-menu)**
  - Stakeholder reviewed and refined category naming. Final approved structure:

  | Top Level | Sub-items |
  |---|---|
  | Ethnic Wear | Kurti, Kurti Set, Suits, Indo Western |
  | Western Wear | Tops, Casual Top, Korean Top, Shirt, Blouse, Bodycon |
  | Dresses & Gowns | Casual Dress, Party Gown, Maxi Dress |
  | Cord Sets | Cord Set |
  | Bottoms | Formal Pants, Palazzo, Skirt |
  | Innerwear | Inners, Panties |
  | Beauty & Care | Skin Care, Face Wash, Body Lotion, Hair Mask, Face Mask |
  | Contact | /pages/contact |

  - **Naming rationale:**
    - "Dresses" → "Dresses & Gowns" — matches Myntra/Nykaa conventions; clearer since Gown and Maxi are distinct silhouettes
    - "Single Piece" → "Casual Dress" — more descriptive and searchable
    - "Gown" → "Party Gown" — distinguishes from Ethnic Gown / Kurti category
    - "Maxi" → "Maxi Dress" — consistent naming with Dress suffix
    - "Bottom" → "Formal Pants" — stakeholder confirmed "Bottom" = formal pant; rename is clearer for customers
    - "Plazo" → "Palazzo" — corrected to standard spelling used on all major platforms

- 2026-03-02 — **DEPLOYED: Full mega-menu navigation + Contact page**
  - Token regenerated: `shpat_***REDACTED***` (app version: `pookiestyle-project-4`)
  - Nav scopes resolved — requires API version `2026-01` (not `2025-01`)
  - **Main menu built** via GraphQL `menuUpdate` mutation — 9 top-level items, 25 sub-collection links
  - **Contact page deployed** at `/pages/contact` with phone, WhatsApp, email, address, business hours, exchange policy, Instagram link
  - Contact page redesigned with compact horizontal cards for better desktop/mobile fit
  - Key technical finding: GraphQL variable-based mutations silently fail for `menuUpdate`; inline syntax works

---

- 2026-03-02 — **CREATED: AI Product Creation Tool HLD (`docs/product-creation-tool.md`)**
  - Searched all workspace files — confirmed NO existing HLD for this tool existed
  - Documented full requirements based on stakeholder discussion:
    - Admin uploads raw phone photos (hand/hanger/mannequin) + enters price, sizes, category
    - AI analyzes photo (GPT-4 Vision) → extracts color, fabric, style, garment type
    - AI generates 6 professional product images (DALL-E 3): front, back, side, zoom, full-outfit, styled background
    - Background is generated to complement garment color for maximum visibility
    - Full outfit: if top → generates matching bottom; if bottom → generates matching top
    - AI generates product name, description, tags, SEO metadata (GPT-4o)
    - Admin previews everything → can edit/regenerate → approves → product created on Shopify
  - Tech stack: Python FastAPI backend + HTML/Tailwind frontend + OpenAI APIs + Shopify GraphQL
  - Estimated cost: ~₹33 per product (~$0.38)
  - Implementation plan: 4 phases over 5 weeks (MVP → AI images → Polish → Advanced)

Notes:
- The stakeholder is the sole decision maker.
- All files are authored for a single production Shopify environment.