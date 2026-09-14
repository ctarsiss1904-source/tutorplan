"""Create Cloudflare Pages static configuration without deploying anything."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'output'
def main():
 deploy=json.loads((ROOT/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'))
 ready=[x for x in deploy if x['deploy_ready']]
 if len(ready)!=1270:raise RuntimeError(f'Expected 1270 ready records, got {len(ready)}')
 # Static rewrites make each no-trailing-slash canonical resolve directly to its index file.
 lines=['# Generated from general_tutor deploy inventory. Do not edit individual rules.','# Cloudflare Pages applies redirect rules before serving static assets.']
 for item in ready:
  route=item['canonical_url'].replace('https://tutorplan.co.kr','')
  target='/'+item['output_path'].replace('output/','')
  lines.append(f'{route} {target} 200')
 (OUT/'_redirects').write_text('\n'.join(lines)+'\n',encoding='utf8')
 headers='''# Static security and cache baseline for Cloudflare Pages.
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/robots.txt
  Cache-Control: public, max-age=300

/sitemap.xml
  Cache-Control: public, max-age=300

/sitemap-general-tutor.xml
  Cache-Control: public, max-age=300
'''
 (OUT/'_headers').write_text(headers,encoding='utf8')
 print({'redirect_rewrites':len(ready),'headers_rules':4})
if __name__=='__main__':main()
