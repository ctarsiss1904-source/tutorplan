# TutorPlan frontend

The Python pipeline remains the source for Excel analysis, region processing, content, validation, and deploy inventory. This Next.js app reads the generated JSON at build time.

## Update flow

1. Update F–J in `과외.xlsx`.
2. Run `python apply_anchor_and_content_policy.py`.
3. Confirm newly READY inventory entries.
4. Run the general tutor content generator and quality validators.
5. Update the deploy inventory.
6. Run `npm run build` in this directory.

Do not hand-add tutor routes: deploy-ready JSON determines all static tutor routes.
