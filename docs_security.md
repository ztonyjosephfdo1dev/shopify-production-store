# Security Notes

Date: 2026-02-26

## Secrets & Credentials
- Never commit API keys, access tokens, or passwords to the repository.
- Use GitHub Secrets for storing values used by GitHub Actions:
  - `SHOPIFY_STORE` → `udfphb-uk.myshopify.com`
  - `SHOPIFY_API_TOKEN` → Theme Access password (`shptka_...`) — get from Shopify Admin → Apps → Theme Access
  - `SHOPIFY_THEME_ID` → `135917666402`
- Theme Access password is generated at: Shopify Admin → Apps → Theme Access → Generate password
- Token is shown only once — store it in GitHub Secrets immediately after generating.
- Rotate the Theme Access password periodically by deleting and regenerating in the Theme Access app.

## Access Control
- Protect `main` / `production` branches.
- Use least privilege for Shopify Admin: restrict staff accounts to necessary permissions.

## Recommendations
- Rotate API keys periodically.
- Use multi-factor authentication (MFA) on the Shopify account and GitHub account.
- Audit installed apps and remove unused ones.