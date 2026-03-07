# Security Notes

Date: 2026-02-26 | Updated: 2026-03-07

---

## 🏭 Production Web Application — Security Standards

This system is a **live production web application** serving real customers at `pookiestyle.in`. All backend operations run on Google Cloud Functions (GCP). The following standards apply to all future development:

### Token & Credential Management
- **No manual token rotation** — the backend must self-heal. All 401s are handled automatically via runtime token refresh (Client Credentials Grant). No developer intervention required.
- **No secrets in code or git** — all credentials live exclusively in GCP environment variables (`.env.yaml`, gitignored). Committed files must never contain real keys.
- **No hardcoded fallbacks** — credentials must always come from `os.environ`. Default values in code must be empty strings, never real tokens.
- **Auto-refresh pattern** — any service calling an external API must catch 401, refresh the credential, and retry once before surfacing an error to the user.

### Deployment Standards
- Always deploy via `deploy_script.py` — never manually edit GCP env vars in the console.
- All code changes must go through git before deployment.
- Test the endpoint after every deploy (`curl.exe -X POST ... -d '{}'` → expect `400`, not `401` or `500`).

### Code Standards
- Services must be stateless and idempotent where possible.
- All external API calls must have explicit timeouts set.
- All errors surfaced to the user must be human-readable (no raw exception stack traces in API responses).
- Sensitive fields (`SHOPIFY_CLIENT_SECRET`, API keys) must never appear in logs.

### What NOT to Do
| Do NOT | Why |
|---|---|
| Manually update GCP env vars in the Cloud Console | Bypasses git history, creates config drift |
| Commit `.env.yaml` or any file with real keys | GitHub secret scanning will block the push |
| Hardcode a token in source code as a temporary fix | Creates a security vulnerability in production |
| Skip deployment verification after a token change | A broken token silently fails all product creation |

---

## ⚠️ IMPORTANT: How Shopify API Credentials Work

### Partners Dashboard App (pookiestyle-project) ✅ WORKING
- **Client ID:** `14a5489a839a93787909313b3955e940`
- **Client Secret:** `shpss_***REDACTED***`
- **App location:** `dev.shopify.com/dashboard/177855543/apps`
- **Current Active Token:** `shpat_***REDACTED***` (generated 2026-03-02, version: pookiestyle-project-4)

### ✅ Token Refresh — NOW FULLY AUTOMATIC (2026-03-07)

As of `2026-03-07`, the backend (`shopify_service.py`) **automatically refreshes the token at runtime** when a 401 is received. No manual steps, no redeploy needed.

**How it works:**
1. Request hits GCP → `shopify_service.py` calls Shopify with the stored token
2. If Shopify returns `401` → service calls `POST /admin/oauth/access_token` using `SHOPIFY_CLIENT_ID` + `SHOPIFY_CLIENT_SECRET` (stored in GCP env vars)
3. Fresh token is obtained in ~100ms → original request retried → succeeds
4. User never sees any error

**Manual regeneration (only if GCP env vars are wiped/lost):**
```powershell
$body = @{
    client_id = "14a5489a839a93787909313b3955e940"
    client_secret = "shpss_***REDACTED***"
    grant_type = "client_credentials"
} | ConvertTo-Json
Invoke-RestMethod -Uri "https://udfphb-uk.myshopify.com/admin/oauth/access_token" -Method POST -Body $body -ContentType "application/json"
```
Run this in PowerShell anytime the token expires — it instantly returns a new `access_token`.

---

## 🔴 INCIDENT LOG — Token 401 Unauthorized (2026-03-02)

### What happened
Both tokens (`shpat_` and `shptka_`) started returning 401 Unauthorized. All Admin API and theme operations were blocked.

### Root cause
The app (`pookiestyle-project`) at `dev.shopify.com` had released a new version (`all_orders_access`). Releasing a new app version in the Partners Dashboard **invalidates the previously issued access token**.

### What did NOT work
| Approach | Why it failed |
|---|---|
| Use Client ID + Secret directly as Basic Auth | Not valid — they are not API credentials |
| OAuth flow with `redirect_uri=https://httpbin.org/get` | `redirect_uri is not whitelisted` error |
| Adding nav scope checkboxes in Shopify Admin | Not available — this is a Partners app, not Admin custom app |
| Creating new custom app from Shopify Admin | Wrong location — this app lives in Partners Dashboard |

### ✅ What WORKED — Client Credentials Grant
Partners Dashboard apps support the **OAuth 2.0 Client Credentials Grant** to generate a token directly using just Client ID + Secret. No redirect URL, no browser OAuth needed.

```powershell
# Run this in PowerShell any time the token expires or returns 401
$body = @{
    client_id     = "14a5489a839a93787909313b3955e940"
    client_secret = "shpss_***REDACTED***"
    grant_type    = "client_credentials"
} | ConvertTo-Json

$r = Invoke-RestMethod -Uri "https://udfphb-uk.myshopify.com/admin/oauth/access_token" `
     -Method POST -Body $body -ContentType "application/json"

Write-Host "New Token: $($r.access_token)"
Write-Host "Scopes: $($r.scope)"
```

### After getting new token — verify it works
```powershell
$headers = @{ "X-Shopify-Access-Token" = "PASTE_NEW_TOKEN_HERE" }
$shop = Invoke-RestMethod -Uri "https://udfphb-uk.myshopify.com/admin/api/2025-01/shop.json" -Headers $headers
Write-Host $shop.shop.name   # Should print: Pookie Style
```

### When does this need to be repeated?
- Every time a **new version is released** in the Partners Dashboard app
- If Shopify revokes the token for inactivity or security reasons
- If the token returns 401 for any API call

---

### ✅ Nav Scopes Status (RESOLVED 2026-03-02)
- Nav scopes added in app version `pookiestyle-project-4` → released → token regenerated
- **Important:** Use API version `2026-01` (not `2025-01`) for menu operations — older versions return ACCESS_DENIED even with correct scopes
- Mega-menu fully built via `menuUpdate` GraphQL mutation with 9 top-level items and 25 sub-collection links
- To update menus in the future, use the inline GraphQL mutation syntax (variable-based syntax silently fails)

### Admin Custom App (RECOMMENDED — Simplest)
- Created at: `https://udfphb-uk.myshopify.com/admin/settings/apps/development`
- Gives a **static `shpat_...` token** — no OAuth needed, no redirect URLs, never expires.
- **Required scopes for this project:**
  - `read_themes`, `write_themes`
  - `read_content`, `write_content`
  - `read_products`, `write_products`
  - `read_online_store_navigation`, `write_online_store_navigation`
- Token is shown once — save it immediately.

### Theme Access Token (`shptka_...`)
- Separate token for theme-only CLI operations (Shopify CLI push/pull)
- Generated at: Shopify Admin → Apps → Theme Access → Generate password
- Used in `shopify.theme.toml` and GitHub Actions as `SHOPIFY_API_TOKEN`

---

## Store & Theme Reference
- **Store:** `udfphb-uk.myshopify.com` | Custom domain: `pookiestyle.in`
- **Theme ID:** `135917666402` (Rise theme — live)
- **GitHub Repo:** `ztonyjosephfdo1dev/shopify-production-store`

---

## MCP Servers — No Auth Needed
- Dev MCP (`@shopify/dev-mcp`): Documentation only — **no credentials needed**
- Storefront MCP (`udfphb-uk.myshopify.com/api/mcp`): Public endpoint — **no credentials needed**
- See `docs_mcp-servers.md` for full setup.

---

## GitHub Secrets (for CI/CD)
- `SHOPIFY_STORE` → `udfphb-uk.myshopify.com`
- `SHOPIFY_API_TOKEN` → Theme Access token (`shptka_...`) from Theme Access app
- `SHOPIFY_THEME_ID` → `135917666402`

---

## Access Control
- Protect `main` / `production` branches.
- Use least privilege for Shopify Admin: restrict staff accounts to necessary permissions.
- Use multi-factor authentication (MFA) on the Shopify account and GitHub account.
- Audit installed apps and remove unused ones.
- Rotate tokens periodically by creating a new Admin Custom App.