# Deployment Checklist

Use this checklist before publishing changes to the production Shopify store.

- [ ] Duplicate the current live theme in Shopify Admin (backup).
- [ ] Ensure all changes are committed to Git and pushed.
- [ ] Confirm branch protection for `main`/`production`.
- [ ] Build assets locally and confirm successful build.
- [ ] Run local preview (shopify theme serve) and validate changes.
- [ ] Update version or changelog entry.
- [ ] Ensure GitHub Actions secrets are present (if using CI).
- [ ] Push changes to repository and deploy to duplicate theme.
- [ ] Manually verify duplicate theme in Shopify preview.
- [ ] Publish duplicate theme from Shopify Admin only when verified.
- [ ] Monitor production for 24 hours for regressions.
- [ ] Add deployment notes to `docs/changelog.md`.