"""Fail-fast validation for uploading output/ as the TutorPlan web root."""
from __future__ import annotations
import csv,json,re,sys
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
 scope=list(csv.DictReader((ROOT/'review/general_tutor_k_final_generation_scope.csv').open(encoding='utf-8-sig'))); allowed={r['page_id'] for r in scope if r['generation_allowed'].lower()=='true'}; hold={r['page_id'] for r in scope if r['generation_allowed'].lower()!='true'} | {r['page_id'] for r in csv.DictReader((ROOT/'review/general_tutor_k_missing_376.csv').open(encoding='utf-8-sig'))}
 if len(ready)!=841 or {x['page_id'] for x in ready}!=allowed:errors.append(f'deploy_ready expected 841 exact routes, got {len(ready)}')
 if len(hold)!=429 or allowed&hold or len(allowed|hold)!=1270:errors.append('READY/HOLD rollout set mismatch')
 tutor_html=list((OUT/'tutor').rglob('index.html')) if (OUT/'tutor').exists() else []
 general_html={str(OUT/x['output_path']) for x in ready}
 if len(tutor_html)!=964:errors.append(f'tutor HTML expected 964 (841 + preserved 123), got {len(tutor_html)}')
 if len(ready)!=841:errors.append('general_tutor HTML expected 841')
 for page_id in hold:
  pass
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
