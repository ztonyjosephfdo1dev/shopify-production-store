# Runbook — Emergency & Routine Operations

Date: 2026-03-10 (updated)
Owner: ztonyjosephfdo1dev

## Purpose
Quick reference for responding to common incidents and performing routine operations — covering both the Shopify theme and the AI Product Creation Cloud Function.

---

## 1. Theme Incidents

### 1.1 Site down or major visual regression
- Immediately revert to last known-good theme:
  - If duplicate theme already exists: Publish the known-good duplicate from Shopify Admin.
  - If using Git: checkout the previous commit/tag → run `python push_theme.py` → publish.
- Inform stakeholders; document in `docs_discussion-log.md`.

### 1.2 Broken checkout or payment issues
- Stop further deployments.
- Check third-party app statuses (Shopify Status page).
- Revert to previous theme if problem started after a recent change.

---

## 2. AI Product Creation Tool — Cloud Function

### 2.1 Product creation fails (UI shows error)

**Step 1 — Check GCP logs (fastest diagnosis):**
```
Google Cloud Console → Cloud Functions → create-product → Logs
```
Filter: last 30 minutes. Look for Python tracebacks.

**Step 2 — Common causes and fixes:**

| Error in logs | Cause | Fix |
|---|---|---|
| `AuthenticationError` / `401` | OpenAI API key invalid or quota exceeded | Check [platform.openai.com](https://platform.openai.com) → Usage. Top up or rotate key. |
| `insufficient_quota` | OpenAI balance = $0 | Add credits at platform.openai.com → Billing |
| `Shopify 403` / `ACCESS_DENIED` | Shopify token expired or revoked | Regenerate token in Shopify Admin → Apps → Develop apps → pookie-automation |
| `Timeout` / `DeadlineExceeded` | Image generation took >300s | Retry with `quality=low`. Check OpenAI status page. |
| `PIL` / `image_utils` error | Malformed image returned from OpenAI | Check image size/format. Retry. |
| `stagedUploadsCreate` error | Shopify image upload failed | Check Shopify API status. Retry. |

### 2.2 Update API keys on the Cloud Function
```bash
gcloud functions deploy create-product \
  --region=asia-south1 \
  --update-env-vars OPENAI_API_KEY=sk-NEW-KEY
```
Replace only the changed variable. Others remain untouched.

### 2.3 Redeploy the Cloud Function (after code changes)
```bash
cd product-tool
python ../deploy_script.py
```
Takes ~2 minutes. Zero downtime (GCP does rolling deploy).

### 2.4 Push theme changes to Shopify
```bash
python push_theme.py
```
Pushes only `pookie-product-creator.liquid` + CSS to theme `135917666402`.

### 2.5 Switch image provider
To test a different image backend, update the Cloud Function env var:
```bash
# Use OpenAI (default)
gcloud functions deploy create-product --region=asia-south1 \
  --update-env-vars IMAGE_PROVIDER=openai

# Use legacy Replicate VTON (stub — needs full implementation)
gcloud functions deploy create-product --region=asia-south1 \
  --update-env-vars IMAGE_PROVIDER=replicate
```

### 2.6 Upgrade image model
To try a newer OpenAI image model without code changes:
```bash
gcloud functions deploy create-product --region=asia-south1 \
  --update-env-vars IMAGE_MODEL=gpt-image-1
```

---

## 3. Cost Monitoring

### 3.1 Check OpenAI spend
1. Go to [platform.openai.com](https://platform.openai.com) → Usage
2. Filter by date. Watch for unexpected spikes.

### 3.2 Cost per product (reference)

| Quality | Image cost | Text cost | Total |
|---|---|---|---|
| Low | ~$0.006 × 1 image | ~$0.0005 | **~₹0.55** |
| Medium | ~$0.015 × 1 image | ~$0.0005 | **~₹1.30** |
| High | ~$0.052 × 1 image | ~$0.0005 | **~₹4.50** |

GCP hosting: **₹0** (always-free tier).

### 3.3 Set OpenAI spend limit (recommended)
- platform.openai.com → Settings → Limits
- Set monthly hard limit: $5 (covers ~350 high-quality products)

---

## 4. Routine Tasks

- **Weekly:** Verify GCP logs are clean; check OpenAI balance.
- **Before any theme deployment:** Export a theme backup from Shopify Admin.
- **Before any Cloud Function deployment:** Run a manual test on a draft product.
- **Monthly:** Review installed Shopify apps and permissions; check GCP free-tier usage dashboard; update changelog.

---

## 5. Contacts & Resources

| Resource | Link |
|---|---|
| GCP Console | [console.cloud.google.com](https://console.cloud.google.com) → Project: `pookie-style-automation` |
| Cloud Function | Region: `asia-south1` → Function: `create-product` |
| OpenAI Usage | [platform.openai.com/usage](https://platform.openai.com/usage) |
| Shopify Admin | [udfphb-uk.myshopify.com/admin](https://udfphb-uk.myshopify.com/admin) |
| Theme ID | `135917666402` |

## 6. Post-incident

- Document event in `docs_discussion-log.md`.
- Update `docs_changelog.md` if a fix was deployed.
- Run root cause analysis for any outage > 15 minutes.