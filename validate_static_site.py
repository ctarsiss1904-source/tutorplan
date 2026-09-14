"""Validate static output links, canonicals, sitemap, and ready inventory."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'output';DOMAIN='https://tutorplan.co.kr'
def target_exists(href):
 if href in ('','/'):return (OUT/'index.html').exists()
 p=OUT/href.lstrip('/')
 return (p/'index.html').exists() or p.exists()
def main():
 files=list(OUT.rglob('index.html'));broken=[];canonical=[];route_errors=[]
 for f in files:
  text=f.read_text(encoding='utf8');route='/' + f.parent.relative_to(OUT).as_posix() if f.parent!=OUT else '/'
  for href in re.findall(r'href="([^"]+)"',text):
   if href.startswith('/') and not href.startswith('//') and not target_exists(href):broken.append((str(f.relative_to(OUT)),href))
  found=re.findall(r'<link rel="canonical" href="([^"]+)">',text)
  expected=DOMAIN+route
  if route.startswith('/regions/') or route in ('/contact','/privacy','/terms','/tutoring','/regions'): expected+='/'
  if found:
   canonical+=found
   if found[0] != expected:route_errors.append((str(f.relative_to(OUT)),found[0],expected))
 deploy=json.loads((ROOT/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'));ready=[x for x in deploy if x['deploy_ready']]
 missing=[x['page_id'] for x in ready if not (ROOT/x['output_path']).exists()]
 sitemap=(OUT/'sitemap-general-tutor.xml').read_text(encoding='utf8');locs=re.findall(r'<loc>(.*?)</loc>',sitemap)
 index=(OUT/'sitemap.xml').read_text(encoding='utf8')
 result={'html_files':len(files),'broken_internal_links':len(broken),'canonical_errors':len(route_errors),'duplicate_canonical':len(canonical)-len(set(canonical)),'ready':len(ready),'ready_missing_output':len(missing),'sitemap_general_urls':len(locs),'sitemap_mismatch':len(set(locs)^{x['canonical_url'] for x in ready}),'sitemap_index_ok':DOMAIN+'/sitemap-general-tutor.xml' in index,'robots_ok':DOMAIN+'/sitemap.xml' in (OUT/'robots.txt').read_text(encoding='utf8')}
 (ROOT/'review/static_site_validation.json').write_text(json.dumps({'result':result,'broken':broken[:100],'canonical_route_errors':route_errors[:100]},ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
