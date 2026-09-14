# Cloudflare Pages deployment checklist

## Project settings

- [ ] Framework preset: **None / Static HTML**
- [ ] Build command: **empty**
- [ ] Build output directory: **output**
- [ ] No Node.js build step configured
- [ ] `python validate_predeploy.py` reports PASS
- [ ] `python prepare_cloudflare_pages.py` reports 1,270 rewrites

## Custom domain and redirects

- [ ] Add `tutorplan.co.kr` in Pages **Custom domains** before DNS changes.
- [ ] For the apex domain, move the zone nameservers to Cloudflare only when ready.
- [ ] Wait for the apex custom domain to become active.
- [ ] Add `www.tutorplan.co.kr` as a custom domain.
- [ ] Create a Bulk Redirect or Redirect Rule: `https://www.tutorplan.co.kr/*` → `https://tutorplan.co.kr/:splat`, 301, preserve query strings.
- [ ] Enable HTTP-to-HTTPS redirect at the Cloudflare zone level.
- [ ] Do not add an SPA fallback or an `/* /index.html 200` rule.

## Post-deploy URL checks

- [ ] `https://tutorplan.co.kr/`
- [ ] `https://tutorplan.co.kr/regions/`
- [ ] A trailing-slash-free deploy-inventory tutor URL
- [ ] A `/regions/…/` directory URL
- [ ] `https://tutorplan.co.kr/sitemap.xml`
- [ ] `https://tutorplan.co.kr/sitemap-general-tutor.xml`
- [ ] `https://tutorplan.co.kr/robots.txt`
- [ ] A non-existent route returns HTTP 404 and `404.html`
- [ ] A preserved one of the original 123 sample URLs
- [ ] A nationwide general tutor URL
- [ ] Canonical host is `https://tutorplan.co.kr`

## Search readiness

- [ ] Confirm sitemap index references the general tutor sitemap.
- [ ] Confirm robots references the sitemap index.
- [ ] Register the HTTPS property and submit the sitemap only after all production URL checks pass.
