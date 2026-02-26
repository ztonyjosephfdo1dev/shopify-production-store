# Rollback Flow

When a deployment causes critical issues, follow these steps:

1. Identify the last known-good theme (duplicate) or commit SHA.
2. If duplicate theme exists:
   - Publish that duplicate from Shopify Admin.
3. If using Git:
   - git checkout <good-commit>
   - push to repository and deploy to a duplicate theme via Shopify CLI
   - publish the duplicate theme after verification
4. Document incident in `docs/discussion-log.md` and `docs/changelog.md`.
5. Perform root cause analysis.