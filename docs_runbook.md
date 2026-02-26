# Runbook — Emergency & Routine Operations

Date: 2026-02-25  
Owner: ztonyjosephfdo1dev

## Purpose
Quick reference for responding to common incidents and performing routine operations.

## Common Incidents & Steps

1. Site down or major visual regression
   - Immediately revert to last known-good theme:
     - If duplicate theme already exists: Publish the known-good duplicate from Shopify Admin.
     - If using Git: checkout the previous commit/tag → deploy to duplicate theme → publish.
   - Inform stakeholders (for single stakeholder, follow own process and document incident).

2. Broken checkout or payment issues
   - Stop further deployments.
   - Check third-party app statuses.
   - Revert to previous theme if problem started after recent change.

3. Data export needed urgently
   - Use Shopify Admin export for products, customers, orders.
   - Share/export to secure location.

## Routine Tasks
- Weekly: verify backups exist, test preview of new theme.
- Before any deployment: create duplicate theme and export backup.
- Monthly: review installed apps and permissions, update documentation.

## Contacts
- Primary: `ztonyjosephfdo1dev` (owner)

## Post-incident
- Document event in `docs/discussion-log.md` and update `docs/changelog.md`.
- Run root cause analysis if needed.