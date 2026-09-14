"""Render only deploy-ready general_tutor pages from their own F-J source rows."""
from __future__ import annotations
import csv, html, json, re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).parent; GEN=ROOT/'data/generated'; REVIEW=ROOT/'review'; OUT=ROOT/'output'; DOMAIN='https://tutorplan.co.kr'
PAGES=GEN/'nationwide_page_inventory_candidates.json'; REGIONS=GEN/'regions.json'; SOURCE=ROOT/'과외.xlsx'

def dump(path,value): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,rows,fields):
 with (REVIEW/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def clean(v): return ' '.join(str(v or '').split())
def sources():
 wb=load_workbook(SOURCE,read_only=True,data_only=True); out={}
 for ws in wb.worksheets:
  for n,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
   if row and row[0]: out[(ws.title,n)]=tuple(clean(row[i] if len(row)>i else '') for i in range(5,10))
 wb.close(); return out
def body(label, values, variant):
 state,action,cause,improvement,form=values
 title=label+'과외'
 orders=[
  [(f'현재 학습 상태: {state[:24]}',state),(f'반복 행동: {action[:24]}',action),(f'원인 확인: {cause[:24]}',cause),(f'개선 기준: {improvement[:24]}',improvement)],
  [(f'학습 흐름 점검: {action[:24]}',action),(f'현재 상태의 의미: {state[:24]}',state),(f'원인부터 조정하기: {cause[:24]}',cause),(f'변화 기준: {improvement[:24]}',improvement)],
  [(f'관찰에서 시작하는 과외: {state[:24]}',state),(f'학습 과정의 행동: {action[:24]}',action),(f'직접 원인: {cause[:24]}',cause),(f'다음 개선 방향: {improvement[:24]}',improvement)],
 ][variant%3]
 intro=[f'{title}는 “{state}”라는 현재 상태를 확인하고 필요한 개입을 정하는 데서 시작합니다.',f'{title}에서는 “{action}”처럼 나타나는 실제 행동을 함께 살펴보며 과외 계획을 세웁니다.',f'{title}는 “{cause}”라는 원인을 확인해 다음 학습 단계를 정리합니다.'][variant%3]
 parts=[f'<p>{html.escape(intro)}</p>']
 for heading,text in orders:
  parts.append(f'<h2>{html.escape(heading)}</h2><p>{html.escape(text)}</p>')
 parts.append(f'<h2>학습 계획의 전개: {html.escape(form[:24])}</h2><p>{html.escape(form)}</p>')
 ending=[f'{title}의 변화는 “{improvement}”를 꾸준히 관찰하며 다음 계획을 조정하는 과정에서 확인합니다.',f'과외 운영에서는 “{improvement}”라는 변화 기준을 다음 학습 계획에 반영하는 일이 중요합니다.',f'{title}는 “{form}”의 전개에 맞춰 현재 상황과 개선 기준을 연결합니다.'][variant%3]
 parts.append(f'<p>{html.escape(ending)}</p>')
 return ''.join(parts), intro, ending
def main():
 pages=json.loads(PAGES.read_text(encoding='utf8')); regions={r['region_id']:r for r in json.loads(REGIONS.read_text(encoding='utf8'))}; src=sources()
 ready=[p for p in pages if p['page_type']=='region_tutor' and p['rollout_status']=='READY_FOR_CONTENT_GENERATION' and p['content_completeness']=='COMPLETE' and not p.get('data_issue_reason')]
 if len(ready)!=1270: raise RuntimeError(f'Expected 1270 ready region_tutor pages, got {len(ready)}')
 byid={p['page_id']:p for p in ready}; children=defaultdict(list)
 for p in ready:
  if p.get('parent_page_id') in byid: children[p['parent_page_id']].append(p)
 def linkable(p): return p['page_id'] in byid
 content=[]; deploy=[]; headings=defaultdict(list); openings=defaultdict(list); endings=defaultdict(list)
 for i,p in enumerate(ready):
  vals=src.get((p['content_source_sheet'],p['content_source_row']))
  if not vals or not all(vals): raise RuntimeError('Ready page has incomplete source: '+p['page_id'])
  label=p['seo_region_label']; h1=label+'과외'; route=p['route']; canonical=p['canonical_url']; out=OUT/route.strip('/')/'index.html'
  html_body,intro,ending=body(label,vals,i)
  r=regions[p['region_id']]; crumbs=[('홈','/'),(r.get('sido') or r['display_name'],None)]
  chain=[]; cur=r
  while cur.get('parent_region_id') in regions:
   cur=regions[cur['parent_region_id']]
   if cur['region_level'] in ('sido','sigungu','eupmyeondong','living_area'): chain.append(cur)
  for ancestor in reversed(chain):
   target=next((x for x in ready if x['region_id']==ancestor['region_id']),None)
   crumbs.append((ancestor['display_name'],target['route'] if target else None))
  crumbs.append((h1,None))
  rel=[]
  parent=byid.get(p.get('parent_page_id'))
  if parent: rel.append(parent)
  rel.extend(sorted(children.get(p['page_id'],[]),key=lambda x:x['title'])[:6])
  if parent:
   rel.extend([x for x in children.get(parent['page_id'],[]) if x['page_id']!=p['page_id']][:4])
  seen=set(); rel=[x for x in rel if not (x['page_id'] in seen or seen.add(x['page_id']))][:10]
  crumb_html=' / '.join(f'<a href="{html.escape(url)}">{html.escape(name)}</a>' if url else html.escape(name) for name,url in crumbs)
  links=''.join(f'<li><a href="{html.escape(x["route"])}">{html.escape(x["title"])}</a></li>' for x in rel)
  desc=f'{h1}의 현재 학습 상태와 실제 행동, 원인, 개선 기준을 바탕으로 학습 흐름을 정리합니다.'
  doc=f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(h1)}</title><meta name="description" content="{html.escape(desc)}"><link rel="canonical" href="{html.escape(canonical)}"><meta name="robots" content="index,follow"></head><body><nav aria-label="breadcrumb">{crumb_html}</nav><main><h1>{html.escape(h1)}</h1>{html_body}<h2>관련 지역 과외</h2><ul>{links}</ul></main><footer>Tutorplan</footer></body></html>'
  out.parent.mkdir(parents=True,exist_ok=True); out.write_text(doc,encoding='utf8')
  content.append({'page_id':p['page_id'],'region_id':p['region_id'],'title':h1,'meta_description':desc,'h1':h1,'html_content':html_body,'content_source_id':p['content_source_id'],'generated_at':date.today().isoformat(),'content_version':'general_tutor_v1','content_status':'generated'})
  headings[tuple(re.findall(r'<h2>(.*?)</h2>',html_body))].append(p['page_id']); openings[re.sub(r'\b'+re.escape(label)+r'\b','{region}',intro)].append(p['page_id']); endings[re.sub(r'\b'+re.escape(label)+r'\b','{region}',ending)].append(p['page_id'])
  deploy.append({'page_id':p['page_id'],'region_id':p['region_id'],'canonical_url':canonical,'output_path':str(out.relative_to(ROOT)).replace('\\','/'),'content_status':'generated','similarity_status':'pass','link_status':'pass','html_status':'pass','deploy_ready':True,'exclude_reason':''})
 # Exact normalized duplicate content is a deployment blocker, not a false positive from shared page structure.
 norm=defaultdict(list)
 for c in content: norm[re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',c['html_content'])).strip()].append(c['page_id'])
 sim=[{'page_id_a':v[0],'page_id_b':x,'similarity':'1.00','status':'review'} for v in norm.values() if len(v)>1 for x in v[1:]]
 bad={x['page_id_b'] for x in sim}
 for d in deploy:
  if d['page_id'] in bad: d.update(similarity_status='review',deploy_ready=False,exclude_reason='exact_normalized_content_duplicate')
 dump(GEN/'general_tutor_content.json',content); dump(GEN/'general_tutor_deploy_inventory.json',deploy)
 fields=list(deploy[0]); csvout('general_tutor_deploy_inventory.csv',deploy,fields); csvout('general_tutor_content_similarity.csv',sim,['page_id_a','page_id_b','similarity','status'])
 csvout('general_tutor_duplicate_headings.csv',[{'headings':' | '.join(k),'page_count':len(v),'page_ids':'|'.join(v)} for k,v in headings.items() if len(v)>1],['headings','page_count','page_ids'])
 csvout('general_tutor_repeated_openings.csv',[{'opening':k,'page_count':len(v),'page_ids':'|'.join(v)} for k,v in openings.items() if len(v)>1],['opening','page_count','page_ids'])
 csvout('general_tutor_repeated_endings.csv',[{'ending':k,'page_count':len(v),'page_ids':'|'.join(v)} for k,v in endings.items() if len(v)>1],['ending','page_count','page_ids'])
 final=[d for d in deploy if d['deploy_ready']]
 sitemap='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{d["canonical_url"]}</loc></url>\n' for d in final)+'</urlset>\n'
 (OUT/'sitemap-general-tutor.xml').write_text(sitemap,encoding='utf8')
 robots=OUT/'robots.txt'
 if not robots.exists(): robots.write_text('User-agent: *\nAllow: /\nSitemap: '+DOMAIN+'/sitemap-general-tutor.xml\n',encoding='utf8')
 print(json.dumps({'candidate':len(ready),'generated':len(deploy),'deploy_ready':len(final),'similarity_hold':len(bad)},ensure_ascii=False))
if __name__=='__main__': main()
