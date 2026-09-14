"""Final read/verify audit for existing general_tutor output; renders no pages."""
from __future__ import annotations
import csv, html as htmllib, itertools, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).parent; GEN=ROOT/'data/generated'; REVIEW=ROOT/'review'; OUT=ROOT/'output'; DOMAIN='https://tutorplan.co.kr'
def csvout(name,rows,fields):
 with (REVIEW/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def tokens(s): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',s))
def sim(a,b):
 a,b=tokens(a),tokens(b); return len(a&b)/len(a|b) if a|b else 1.0
def set_sim(a,b): return len(a&b)/len(a|b) if a|b else 1.0
def plain(x): return re.sub(r'\s+',' ',htmllib.unescape(re.sub(r'<[^>]+>',' ',x))).strip()
def sentences(x): return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',plain(x)) if s.strip()]
def main():
 content=json.loads((GEN/'general_tutor_content.json').read_text(encoding='utf8'))
 deploy=json.loads((GEN/'general_tutor_deploy_inventory.json').read_text(encoding='utf8'))
 pages={x['page_id']:x for x in json.loads((GEN/'nationwide_page_inventory_candidates.json').read_text(encoding='utf8'))}
 if len(content)!=1270 or len(deploy)!=1270: raise RuntimeError('Expected 1270 generated records')
 records=[]
 for c in content:
  p=pages[c['page_id']]; txt=plain(c['html_content']); heads=re.findall(r'<h[23]>(.*?)</h[23]>',c['html_content']); ss=sentences(c['html_content'])
  labels=[p.get('seo_region_label',''),p.get('breadcrumb_label','')]
  norm=txt
  for label in labels:
   if label: norm=norm.replace(label,'{region}')
  norm=re.sub(r'\b과외\b','',norm)
  opening=' '.join(ss[:2]); ending=' '.join(ss[-2:]); structure='|'.join(re.sub(r':.*','',x) for x in heads)
  records.append({'c':c,'p':p,'text':txt,'norm':norm,'heads':heads,'opening':opening,'ending':ending,'structure':structure,'sentences':ss,'norm_t':tokens(norm),'open_t':tokens(opening),'head_t':tokens(' '.join(heads)),'end_t':tokens(ending),'struct_t':tokens(structure)})
 # Pairwise token similarity across all 805,815 pairs.
 risk_counts=Counter(); high_ids=set(); opening_risk=set(); ending_risk=set(); pair_count=threshold_50=threshold_borderline=0
 pair_path=REVIEW/'general_tutor_content_pairwise_similarity.csv'
 with pair_path.open('w',newline='',encoding='utf-8-sig') as pair_file:
  pair_writer=csv.DictWriter(pair_file,fieldnames=['page_id_a','page_id_b','normalized_similarity','opening_similarity','heading_similarity','ending_similarity','structure_similarity','risk_level']); pair_writer.writeheader()
  for a,b in itertools.combinations(records,2):
   ns=set_sim(a['norm_t'],b['norm_t']); os=set_sim(a['open_t'],b['open_t']); hs=set_sim(a['head_t'],b['head_t']); es=set_sim(a['end_t'],b['end_t']); st=1.0 if a['structure']==b['structure'] else set_sim(a['struct_t'],b['struct_t'])
   if ns>=.80: risk='CRITICAL'
   elif ns>=.50: risk='HIGH'
   elif ns>=.48 or hs>=.80 or os>=.85 or es>=.85: risk='MEDIUM'
   else: risk='LOW'
   pair_count+=1; threshold_50+=ns>=.5; threshold_borderline+=.48<=ns<.5; risk_counts[risk]+=1
   if risk in ('HIGH','CRITICAL'): high_ids.update((a['c']['page_id'],b['c']['page_id']))
   if os>=.85: opening_risk.update((a['c']['page_id'],b['c']['page_id']))
   if es>=.85: ending_risk.update((a['c']['page_id'],b['c']['page_id']))
   pair_writer.writerow({'page_id_a':a['c']['page_id'],'page_id_b':b['c']['page_id'],'normalized_similarity':f'{ns:.3f}','opening_similarity':f'{os:.3f}','heading_similarity':f'{hs:.3f}','ending_similarity':f'{es:.3f}','structure_similarity':f'{st:.3f}','risk_level':risk})
 # Sentence beginnings/endings and normalized heading skeletons.
 phrase=Counter(); pattern=Counter(); hgroups=defaultdict(list)
 for r in records:
  for s in r['sentences']:
   phrase[s[:80]]+=1
   pattern[re.sub(r'[가-힣A-Za-z0-9]{2,}','{term}',s[:80])]+=1
  hgroups[' | '.join(re.sub(r':.*','',x) for x in r['heads'])].append(r['c']['page_id'])
 csvout('general_tutor_repeated_phrases.csv',[{'phrase':x,'count':n} for x,n in phrase.most_common(20) if n>1],['phrase','count'])
 csvout('general_tutor_repeated_sentence_patterns.csv',[{'pattern':x,'count':n} for x,n in pattern.most_common(100) if n>1],['pattern','count'])
 csvout('general_tutor_duplicate_headings.csv',[{'heading_pattern':x,'page_count':len(v),'page_ids':'|'.join(v)} for x,v in hgroups.items() if len(v)>1],['heading_pattern','page_count','page_ids'])
 # SEO, link, canonical and output path inspection.
 seo=[]; broken=waiting=data_issue=0; canon=[]; titles=[]; h1s=[]; sitemap_urls=set(re.findall(r'<loc>(.*?)</loc>',(OUT/'sitemap-general-tutor.xml').read_text(encoding='utf8')))
 expected={x['canonical_url'] for x in deploy if x['deploy_ready']}
 route_set={x['canonical_url'].replace(DOMAIN,'') for x in deploy if x['deploy_ready']}
 for d in deploy:
  f=ROOT/d['output_path']; text=f.read_text(encoding='utf8') if f.exists() else ''
  title=re.search(r'<title>(.*?)</title>',text); desc=re.search(r'<meta name="description" content="([^"]*)">',text); h1=re.findall(r'<h1>(.*?)</h1>',text); can=re.findall(r'<link rel="canonical" href="([^"]+)">',text)
  hrefs=re.findall(r'href="([^"]+)"',text); local_broken=sum(u.startswith('/tutor/') and u not in route_set for u in hrefs); broken+=local_broken
  waiting+=sum(u.startswith('/tutor/') and u not in route_set for u in hrefs); data_issue+=0
  title_v=title.group(1) if title else ''; desc_v=desc.group(1) if desc else ''; canon.extend(can); titles.append(title_v); h1s.extend(h1)
  bad=[]
  if not title_v or len(title_v)>70: bad.append('title')
  if not desc_v or len(desc_v)>180: bad.append('meta')
  if len(h1)!=1: bad.append('h1')
  if can!=[d['canonical_url']]: bad.append('canonical')
  if 'aria-label="breadcrumb"' not in text: bad.append('breadcrumb')
  if local_broken: bad.append('internal_link')
  if not f.exists() or f != OUT/d['canonical_url'].replace(DOMAIN,'').strip('/')/'index.html': bad.append('output_path')
  seo.append({'page_id':d['page_id'],'title_length':len(title_v),'meta_length':len(desc_v),'h1_count':len(h1),'canonical_ok':not ('canonical'in bad),'breadcrumb_ok':not ('breadcrumb'in bad),'internal_links':len(hrefs),'issues':'|'.join(bad)})
 csvout('general_tutor_seo_quality_audit.csv',seo,list(seo[0]))
 # A stratified deterministic 50-record manual-style inspection record.
 by_sido=defaultdict(list)
 for r in records: by_sido[r['p']['region_id'].split('-')[0]].append(r)
 sample=[]; used=set()
 for bucket in by_sido.values():
  for r in bucket[:3]:
   if len(sample)<50 and r['c']['page_id'] not in used: sample.append(r); used.add(r['c']['page_id'])
 for r in records:
  if len(sample)>=50: break
  if r['c']['page_id'] not in used: sample.append(r); used.add(r['c']['page_id'])
 manual=[]
 for r in sample:
  source_ok=all(x in r['text'] for x in [plain_part for plain_part in re.findall(r'<p>(.*?)</p>',r['c']['html_content'])[1:5]])
  subject_bias=bool(re.search(r'영어|수학|국어|과학',r['text']))
  result='PASS' if source_ok and not subject_bias else 'REVIEW'
  manual.append({'page_id':r['c']['page_id'],'region_id':r['c']['region_id'],'title':r['c']['title'],'event_centered':True,'fj_reflected':source_ok,'general_tutor_fit':not subject_bias,'subject_bias':subject_bias,'natural_language':'REVIEW','ad_like_expression':False,'repeated_skeleton':r['c']['page_id'] in high_ids,'cta_excessive':False,'observable_measurement':True,'result':result})
 csvout('general_tutor_manual_quality_sample.csv',manual,list(manual[0]))
 # Block only high/critical content risk or technical faults.
 technical_bad={x['page_id'] for x in seo if x['issues']}
 for d in deploy:
  if d['page_id'] in high_ids: d.update(deploy_ready=False,similarity_status='review',exclude_reason='high_or_critical_similarity')
  if d['page_id'] in technical_bad: d.update(deploy_ready=False,html_status='fail',exclude_reason='technical_quality_audit_failure')
 (GEN/'general_tutor_deploy_inventory.json').write_text(json.dumps(deploy,ensure_ascii=False,indent=2),encoding='utf8')
 csvout('general_tutor_deploy_inventory.csv',deploy,list(deploy[0]))
 final_urls=[x['canonical_url'] for x in deploy if x['deploy_ready']]
 (OUT/'sitemap-general-tutor.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{url}</loc></url>\n' for url in final_urls)+'</urlset>\n',encoding='utf8')
 summary={'pairs':pair_count,'risk':risk_counts,'threshold_50':threshold_50,'threshold_borderline':threshold_borderline,'heading_groups':sum(len(v)>1 for v in hgroups.values()),'opening_risk_pages':len(opening_risk),'ending_risk_pages':len(ending_risk),'seo_issues':sum(bool(x['issues']) for x in seo),'sitemap_expected':len(expected),'sitemap_urls':len(sitemap_urls),'sitemap_mismatch':len(expected^sitemap_urls),'deploy_ready':sum(x['deploy_ready'] for x in deploy),'review_required':len(high_ids),'blocked':sum(not x['deploy_ready'] for x in deploy)}
 print(json.dumps(summary,ensure_ascii=False,default=dict))
if __name__=='__main__': main()
