# Service Accounts & API Credentials
> ⚠️ This file is committed to git. Do NOT paste actual secrets here.  
> Actual tokens/keys live in `product-tool/.env.yaml` (git-ignored).

---

## Replicate

| Field | Value |
|-------|-------|
| Account type | **Organisation** |
| Org name | `pookie_style` |
| Dashboard | https://replicate.com/pookie_style |
| Billing page | https://replicate.com/account/billing |
| API tokens page | https://replicate.com/account/api-tokens |
| Active token name | `pookie style automation` |
| Token added | 2026-03-08 |
| Billing credit added | $1.00 on 2026-03-08 |
| Auto-reload | Set up recommended (trigger at $0.50 → reload $5) |
| Cost per product | ~$0.012 (1 VTON call + 2 ESRGAN upscales) |

### Models in use
| Model | Purpose | Cost |
|-------|---------|------|
| `prunaai/p-tryon` | Primary VTON — 4-pose grid generation | ~$0.01/run |
| `cuuupid/idm-vton` (version `0513734a...`) | Fallback VTON if p-tryon fails | ~$0.01/run |
| `nightmareai/real-esrgan` (version `f121d640...`) | Upscale 2 grid halves 4× | ~$0.001/run |

### Notes
- Token must be created under the `pookie_style` **org** (not personal account)
- Org switcher is top-left dropdown on replicate.com — confirm it shows `pookie_style` before creating tokens
- Rate limit is lifted once a payment method is on file for the org

---

## OpenAI

| Field | Value |
|-------|-------|
| Account type | Personal |
| Dashboard | https://platform.openai.com |
| API keys page | https://platform.openai.com/api-keys |
| Usage & billing | https://platform.openai.com/account/usage |
| Credit added | $10.00 on 2026-03-08 |
| Cost per product | ~$0.0003 (1 gpt-4o-mini call) |

### Models in use
| Model | Purpose | Fallback order |
|-------|---------|---------------|
| `gpt-4o-mini` | Primary — image analysis + structured JSON | 1st |
| `gpt-4.1-nano` | Fallback if gpt-4o-mini fails | 2nd |
| `gpt-3.5-turbo` | Last resort fallback | 3rd |

---

## Shopify

| Field | Value |
|-------|-------|
| Store domain | `udfphb-uk.myshopify.com` |
| Custom domain | `pookiestyle.in` |
| Theme ID (live) | `135917666402` |
| Admin | https://udfphb-uk.myshopify.com/admin |
| API version | `2026-01` |

---

## Google Cloud Platform (GCP)

| Field | Value |
|-------|-------|
| Project name | `pookie-style-automation` |
| Project ID | `751815335949` |
| Console | https://console.cloud.google.com/project/pookie-style-automation |
| Cloud Function | `create-product` |
| Region | `asia-south1` |
| Runtime | Python 3.12, 512MB, 300s timeout |
| Function URL | `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product` |

---

## GitHub

| Field | Value |
|-------|-------|
| Repo | `ztonyjosephfdo1dev/shopify-production-store` |
| URL | https://github.com/ztonyjosephfdo1dev/shopify-production-store |
| Main branch | `main` |

---

## Google Cloud Storage

| Field | Value |
|-------|-------|
| Bucket | `pookie-style-uploads` |
| Model image | `gs://pookie-style-uploads/models/indian-model-1.jpg` |
| Public URL | `https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg` |
