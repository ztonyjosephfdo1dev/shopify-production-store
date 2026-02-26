# Deployment Flow (Detailed)

1. Prepare
   - Create backup (duplicate theme)
   - Ensure code is merged to `main`
2. Build
   - Build assets locally or via CI
3. Deploy to preview
   - Use Shopify CLI to push to a duplicate theme
4. Validate
   - Manual QA on duplicate theme preview
5. Publish
   - Publish duplicate theme from Shopify Admin
6. Post-deployment
   - Monitor live store, update changelog, document any issues

## Emergency rollback
- Publish previous duplicate theme or deploy previous commit to duplicate and publish.