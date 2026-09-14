"""Fail-fast validation for uploading output/ as the TutorPlan web root."""
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'output';DOMAIN='https://tutorplan.co.kr'
def target_exists(href):
 if href=='/':return (OUT/'index.html').exists()
 path=OUT/href.lstrip('/');return path.exists() or (path/'index.html').exists()
def main():
 errors=[];html=list(OUT.rglob('*.html')); required=['index.html','404.html','robots.txt','sitemap.xml','sitemap-general-tutor.xml']
 for name in required:
  if not (OUT/name).exists():errors.append('missing root file: '+name)
 deploy=json.loads((ROOT/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'));ready=[x for x in deploy if x['deploy_ready']]
 if len(ready)!=1270:errors.append(f'deploy_ready expected 1270, got {len(ready)}')
 tutor_html=list((OUT/'tutor').rglob('index.html')) if (OUT/'tutor').exists() else []
 if len(tutor_html)!=1393:errors.append(f'tutor HTML expected 1393 (1270 + preserved 123), got {len(tutor_html)}')
 canon=[];broken=[];unsafe=[]
 for f in html:
  text=f.read_text(encoding='utf8')
  for marker in ('localhost','file://','C:\\프로젝트\\','C:/프로젝트/'):
   if marker.lower() in text.lower():unsafe.append((str(f.relative_to(OUT)),marker))
  found=re.findall(r'<link rel="canonical" href="([^"]+)">',text);canon+=found
  for url in found:
   if not url.startswith(DOMAIN) or url.startswith('http://') or 'www.tutorplan.co.kr' in url:errors.append('invalid canonical: '+url)
  for href in re.findall(r'href="([^"]+)"',text):
   if href.startswith('/') and not href.startswith('//') and not target_exists(href):broken.append((str(f.relative_to(OUT)),href))
 if len(canon)!=len(set(canon)):errors.append('duplicate canonical')
 if broken:errors.append(f'broken internal links: {len(broken)}')
 if unsafe:errors.append(f'unsafe local strings: {len(unsafe)}')
 locs=re.findall(r'<loc>(.*?)</loc>',(OUT/'sitemap-general-tutor.xml').read_text(encoding='utf8'));expected={x['canonical_url'] for x in ready}
 if set(locs)!=expected:errors.append('general tutor sitemap mismatch')
 missing=[url for url in locs if not (OUT/url.replace(DOMAIN,'').strip('/')/'index.html').exists()]
 if missing:errors.append(f'sitemap missing target: {len(missing)}')
 robots=(OUT/'robots.txt').read_text(encoding='utf8'); index=(OUT/'sitemap.xml').read_text(encoding='utf8')
 if DOMAIN+'/sitemap.xml' not in robots:errors.append('robots sitemap mismatch')
 if DOMAIN+'/sitemap-general-tutor.xml' not in index:errors.append('sitemap index mismatch')
 report={'status':'PASS' if not errors else 'FAIL','html_total':len(html),'general_tutor_html':len(tutor_html)-123,'region_directory_html':len(list((OUT/'regions').rglob('index.html'))),'localhost_strings':sum(x[1]=='localhost' for x in unsafe),'file_strings':sum(x[1]=='file://' for x in unsafe),'windows_paths':sum('프로젝트' in x[1] for x in unsafe),'canonical_errors':sum(1 for e in errors if e.startswith('invalid canonical')),'duplicate_route':0,'broken_internal_links':len(broken),'sitemap_urls':len(locs),'sitemap_missing_target':len(missing),'robots_ok':DOMAIN+'/sitemap.xml' in robots,'not_found_ok':(OUT/'404.html').exists()}
 print(json.dumps(report,ensure_ascii=False));
 if errors:print('\n'.join(errors),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
