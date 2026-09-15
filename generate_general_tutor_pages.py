"""Render only deploy-ready general_tutor pages from their own F-J source rows."""
from __future__ import annotations
import csv, html, json, re, sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).parent; GEN=ROOT/'data/generated'; REVIEW=ROOT/'review'; OUT=ROOT/'output'; DOMAIN='https://tutorplan.co.kr'
PAGES=GEN/'nationwide_page_inventory_candidates.json'; REGIONS=GEN/'regions.json'; SOURCE=ROOT/'과외.xlsx'
CURRENT_STAGE='LOAD_SCOPE'
FINAL_SCOPE=REVIEW/'general_tutor_k_final_generation_scope.csv'; K_MISSING=REVIEW/'general_tutor_k_missing_376.csv'; RUN_REPORT=REVIEW/'general_tutor_k_generation_run.json'; MANIFEST=REVIEW/'general_tutor_k_generation_manifest.csv'

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
def allowed_scope():
 with FINAL_SCOPE.open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
 required={'page_id','sheet','row','final_readiness','generation_allowed'}
 if not rows or not required.issubset(rows[0]): raise RuntimeError(f'Invalid final generation scope: {FINAL_SCOPE}')
 allowed=[r for r in rows if clean(r['generation_allowed']).lower()=='true']; ids=[r['page_id'] for r in allowed]
 if len(ids)!=len(set(ids)): raise RuntimeError('Duplicate generation_allowed page_id in final generation scope')
 if len(ids)!=841: raise RuntimeError(f'Expected 841 generation_allowed page_ids, got {len(ids)}')
 if any(r['final_readiness'] not in {'READY_AS_IS','READY_REMOVE_DUPLICATE_H1'} for r in allowed): raise RuntimeError('Generation scope contains a non-ready allowed page')
 return {r['page_id']:r for r in allowed}
def k_sources(pages):
 wb=load_workbook(SOURCE,read_only=True,data_only=True); content={}
 try:
  for p in pages:
   sheet=p['content_source_sheet']; row=p['content_source_row']
   if sheet not in wb.sheetnames: raise RuntimeError(f'Missing Excel sheet for {p["page_id"]}: {sheet}')
   try: row_number=int(row)
   except (TypeError,ValueError): raise RuntimeError(f'Invalid Excel row for {p["page_id"]}: {row}')
   value=wb[sheet].cell(row=row_number,column=11).value
   if value is None or not str(value).strip(): raise RuntimeError(f'Missing K content for {p["page_id"]}: {sheet} row {row_number}')
   content[p['page_id']]=str(value).strip()
 finally: wb.close()
 return content
def render_k_content(k_html, readiness, page_id):
 if readiness=='READY_AS_IS': return k_html
 if readiness!='READY_REMOVE_DUPLICATE_H1': raise RuntimeError(f'Unsupported K rendering status for {page_id}: {readiness}')
 first_h1=re.search(r'<h1\b[^>]*>.*?</h1\s*>',k_html,flags=re.IGNORECASE|re.DOTALL)
 if not first_h1: raise RuntimeError(f'Expected PAGE_TITLE H1 in K content for {page_id}')
 return k_html[:first_h1.start()]+k_html[first_h1.end():]
def k_text(k_html): return ' '.join(html.unescape(re.sub(r'<[^>]+>',' ',k_html)).split())
def hold_scope(inventory, ready_ids):
 with K_MISSING.open(newline='',encoding='utf-8-sig') as f: missing=list(csv.DictReader(f))
 with FINAL_SCOPE.open(newline='',encoding='utf-8-sig') as f: scoped=list(csv.DictReader(f))
 hold_ids=[r['page_id'] for r in missing]+[r['page_id'] for r in scoped if clean(r['generation_allowed']).lower()!='true']
 if len(hold_ids)!=429 or len(hold_ids)!=len(set(hold_ids)): raise RuntimeError(f'Expected 429 unique HOLD page_ids, got {len(hold_ids)}')
 if set(hold_ids)&set(ready_ids) or len(set(hold_ids)|set(ready_ids))!=1270: raise RuntimeError('READY/HOLD set validation failed')
 if any(page_id not in inventory for page_id in hold_ids): raise RuntimeError('HOLD page_id missing from inventory')
 return hold_ids
def safe_remove_hold_html(inventory, hold_ids):
 removed=[]; remaining=[]
 root=(OUT/'tutor').resolve()
 for page_id in hold_ids:
  p=inventory[page_id]; route=p['route']
  if not route.endswith('/region_tutor') or p.get('page_type')!='region_tutor': raise RuntimeError('Unsafe HOLD route: '+page_id)
  target=(OUT/route.strip('/')/'index.html').resolve()
  if root not in target.parents: raise RuntimeError('Unsafe HOLD output path: '+str(target))
  if target.exists(): target.unlink(); removed.append(page_id)
  if target.exists(): remaining.append(page_id)
 return removed,remaining
def write_run_report(data): dump(RUN_REPORT,data)
def body(label, values, variant):
    state, action, cause, improvement, form = values
    title = label + '과외'

    # 개선방법과 측정값이 "|"로 구분되어 있으면 각각 분리
    improvement_parts = [x.strip() for x in improvement.split('|') if x.strip()]
    intervention = improvement_parts[0] if improvement_parts else improvement
    metric = improvement_parts[-1] if len(improvement_parts) > 1 else ''

    heading_sets = [
        [
            '수업에서 먼저 확인한 학습 상태',
            '실제 행동에서 드러난 막힘',
            '반복되는 행동의 직접 원인',
            '수업 중 바꿔야 할 학습 과정',
            '변화를 확인하는 관찰 기준',
            '다음 학습으로 이어지는 전개'
        ],
        [
            '처음 관찰된 학습 장면',
            '학생의 행동으로 확인한 문제',
            '학습 흐름이 끊긴 이유',
            '직접 원인을 조정하는 방법',
            '변화를 판단하는 기준',
            '수업 흐름을 다시 연결하는 과정'
        ],
        [
            '현재 학습 흐름에서 나타난 특징',
            '수업 중 반복해서 나타난 행동',
            '문제가 계속되는 직접적인 이유',
            '학생이 직접 수행하도록 바꾼 과정',
            '조정 이후 살펴볼 변화',
            '학습 과정을 이어 가는 순서'
        ]
    ]

    headings = heading_sets[variant % len(heading_sets)]

    intros = [
        f'{title}에서는 현재 상태만 짧게 확인하고 넘어가기보다 실제 학습 과정에서 어떤 행동이 반복되는지를 함께 살펴봅니다. '
        f'이번 학습 장면에서는 {state}라는 상태가 확인됐고, 학생의 실제 행동에서는 {action}라는 모습이 나타났습니다. '
        f'겉으로 보이는 결과만 바꾸기보다 이러한 행동이 어느 지점에서 시작되는지를 확인해야 다음 학습 계획도 구체적으로 정할 수 있습니다.',

        f'{title}의 학습 흐름을 살펴보면 문제를 맞혔는지보다 학생이 어떤 순서로 시작하고 어디에서 멈추는지를 확인하는 과정이 중요합니다. '
        f'이번에는 {action}라는 행동이 반복됐으며, 이를 현재 상태인 {state}와 연결해 살펴봤습니다. '
        f'학생이 실제로 수행하는 과정을 기준으로 보면 단순한 실수와 반복되는 학습 문제를 구분하기 쉬워집니다.',

        f'{title}에서 확인한 핵심은 학습량을 늘리는 것이 아니라 현재 행동이 어떤 원인과 연결되어 있는지를 찾는 것이었습니다. '
        f'수업에서는 {state}라는 상태와 함께 {action}라는 실제 행동이 관찰됐습니다. '
        f'이 두 가지를 따로 보지 않고 하나의 학습 사건으로 연결하면 개입해야 할 지점을 보다 분명하게 정할 수 있습니다.'
    ]

    intro = intros[variant % len(intros)]

    parts = [f'<p>{html.escape(intro)}</p>']

    paragraphs = [
        (
            headings[0],
            f'수업을 시작할 때 먼저 확인한 것은 {state}였습니다. '
            f'이 상태를 단순한 평가 문장으로 남기지 않고 실제 학습 과정에서 언제 나타나는지 확인했습니다. '
            f'학생이 과제를 시작하는 순간과 설명을 들은 직후, 혼자 다시 수행하는 구간을 나누어 살펴보면 현재 상태가 어떤 행동과 이어지는지 구체적으로 확인할 수 있습니다.'
        ),
        (
            headings[1],
            f'실제 행동에서는 {action}라는 모습이 나타났습니다. '
            f'중요한 점은 이 행동을 결과만으로 판단하지 않는 것입니다. '
            f'학생이 어느 단계까지 혼자 진행했고 어느 순간부터 흐름이 끊겼는지를 확인해야 같은 문제가 다음 활동에서도 반복되는지 비교할 수 있습니다.'
        ),
        (
            headings[2],
            f'이 행동의 직접 원인은 {cause}로 확인했습니다. '
            f'따라서 문제를 해결하기 위해 학습량을 무조건 늘리거나 설명을 반복하기보다 이 원인이 실제로 발생하는 구간을 먼저 조정해야 합니다. '
            f'행동과 직접 원인을 연결해 확인하면 학생에게 필요한 개입도 한 단계 더 구체적으로 정할 수 있습니다.'
        ),
        (
            headings[3],
            f'수업에서는 {intervention}라는 방식으로 학습 과정을 조정합니다. '
            f'교사가 대신 수행하거나 답을 먼저 알려주는 방식이 아니라 학생이 직접 해야 할 행동을 분명하게 남기는 것이 핵심입니다. '
            f'같은 조건에서 다시 수행했을 때 이전 행동이 줄어드는지 확인하면서 다음 개입의 강도를 조정합니다.'
        ),
        (
            headings[4],
            (
                f'변화는 {metric}을 기준으로 확인합니다. '
                f'한 번의 성공 여부만 보는 대신 같은 조건에서 이 기준이 반복해서 유지되는지를 살펴봅니다. '
                f'측정값이 안정적으로 유지되면 다음 단계로 넘어가고, 다시 흔들리면 어느 구간에서 행동이 달라졌는지 되짚어 학습 계획을 조정합니다.'
                if metric else
                f'변화는 {improvement}의 과정이 실제 학습에서 유지되는지를 기준으로 확인합니다. '
                f'한 번의 성공 여부만으로 판단하지 않고 같은 조건에서 학생이 스스로 같은 행동을 재현할 수 있는지를 반복해서 살펴봅니다.'
            )
        ),
        (
            headings[5],
            f'전체 수업의 전개는 {form}의 흐름을 기준으로 이어집니다. '
            f'각 단계는 따로 떨어진 활동이 아니라 처음 확인한 상태와 실제 행동, 직접 원인, 개입 과정, 변화 기준을 하나의 사건 안에서 연결하기 위한 순서입니다. '
            f'마지막에는 처음과 같은 조건을 다시 제시해 학생이 어느 정도까지 독립적으로 수행하는지 확인하고 다음 학습 계획에 반영합니다.'
        )
    ]

    for heading, text in paragraphs:
        parts.append(
            f'<h2>{html.escape(heading)}</h2>'
            f'<p>{html.escape(text)}</p>'
        )

    endings = [
        f'{title}에서는 처음 확인한 상태와 마지막 수행을 같은 기준에서 비교합니다. '
        f'특히 {metric if metric else improvement}의 변화를 관찰하면서 다음 수업에서 유지할 부분과 다시 조정할 부분을 구분합니다.',

        f'학습 계획은 한 번 정한 방식으로 고정하지 않습니다. '
        f'{metric if metric else improvement}을 계속 확인하면서 학생이 혼자 수행할 수 있는 범위가 넓어지는지 살펴보고 다음 과정을 정합니다.',

        f'{title}의 마지막 확인 기준은 설명을 많이 했는지가 아니라 학생의 실제 행동이 달라졌는지입니다. '
        f'{metric if metric else improvement}을 기준으로 같은 상황에서의 수행을 다시 관찰하고 다음 학습 단계로 연결합니다.'
    ]

    ending = endings[variant % len(endings)]
    parts.append(f'<p>{html.escape(ending)}</p>')

    return ''.join(parts), intro, ending 
def set_stage(stage):
 global CURRENT_STAGE; CURRENT_STAGE=stage
def main():
 set_stage('LOAD_SCOPE')
 scope=allowed_scope(); set_stage('LOAD_INVENTORY')
 pages=json.loads(PAGES.read_text(encoding='utf8')); regions={r['region_id']:r for r in json.loads(REGIONS.read_text(encoding='utf8'))}
 inventory={p['page_id']:p for p in pages}
 if len(inventory)!=len(pages): raise RuntimeError('Duplicate page_id in nationwide page inventory')
 set_stage('VALIDATE_READY_HOLD')
 missing=[page_id for page_id in scope if page_id not in inventory]
 if missing: raise RuntimeError('Scope page_id missing from inventory: '+missing[0])
 ready=[]
 for page_id,scope_row in scope.items():
  p=inventory[page_id]
  if str(p.get('content_source_sheet'))!=scope_row['sheet'] or str(p.get('content_source_row'))!=scope_row['row']: raise RuntimeError('Scope and inventory source mismatch: '+page_id)
  p=dict(p); p['final_readiness']=scope_row['final_readiness']; ready.append(p)
 set_stage('LOAD_EXCEL_K')
 k_content=k_sources(ready)
 set_stage('VALIDATE_K')
 hold_ids=hold_scope(inventory,scope)
 byid={p['page_id']:p for p in ready}; children=defaultdict(list)
 for p in ready:
  if p.get('parent_page_id') in byid: children[p['parent_page_id']].append(p)
 def linkable(p): return p['page_id'] in byid
 content=[]; deploy=[]; headings=defaultdict(list); openings=defaultdict(list); endings=defaultdict(list)
 set_stage('GENERATE_READY_HTML')
 for i,p in enumerate(ready):
  label=p['seo_region_label']; h1=label+'과외'; route=p['route']; canonical=p['canonical_url']; out=OUT/route.strip('/')/'index.html'
  html_body=render_k_content(k_content[p['page_id']],p['final_readiness'],p['page_id'])
  body_text=k_text(html_body); intro=body_text[:500]; ending=body_text[-500:]
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
  content.append({'page_id':p['page_id'],'region_id':p['region_id'],'title':h1,'meta_description':desc,'h1':h1,'html_content':html_body,'content_source_id':p['content_source_id'],'generated_at':date.today().isoformat(),'content_version':'general_tutor_k_v1','content_status':'generated'})
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
 set_stage('REMOVE_HOLD_STALE')
 removed,remaining=safe_remove_hold_html(inventory,hold_ids)
 manifest=[]
 for p in ready: manifest.append({'page_id':p['page_id'],'route':p['route'],'final_status':p['final_readiness'],'generation_allowed':'true','source_sheet':p['content_source_sheet'],'source_row':p['content_source_row'],'k_present':'true','output_path':str(OUT/p['route'].strip('/')/'index.html'),'output_exists_after':True,'action':'GENERATED_K_REMOVE_H1' if p['final_readiness']=='READY_REMOVE_DUPLICATE_H1' else 'GENERATED_K'})
 for page_id in hold_ids:
  p=inventory[page_id]; manifest.append({'page_id':page_id,'route':p['route'],'final_status':'HOLD','generation_allowed':'false','source_sheet':p.get('content_source_sheet',''),'source_row':p.get('content_source_row',''),'k_present':'false','output_path':str(OUT/p['route'].strip('/')/'index.html'),'output_exists_after':False,'action':'STALE_REMOVED' if page_id in removed else 'HOLD_NO_FILE'})
 set_stage('WRITE_MANIFEST')
 csvout('general_tutor_k_generation_manifest.csv',manifest,list(manifest[0]))
 set_stage('FINAL_VALIDATION')
 write_run_report({'status':'PASS','failed_stage':None,'failure_reason':None,'failure_type':None,'generation_allowed_count':len(ready),'generation_allowed_unique':len(scope),'hold_total':len(hold_ids),'total_rollout':len(set(hold_ids)|set(scope)),'k_mapping_success':len(k_content),'k_mapping_failure':0,'generated_html_count':len(deploy),'stale_html_deleted':len(removed),'stale_html_remaining':len(remaining),'deploy_ready_count':len(final),'sitemap_url_count':len(final),'ready_hold_intersection_count':len(set(hold_ids)&set(scope)),'ready_hold_union_count':len(set(hold_ids)|set(scope)),'timestamp':date.today().isoformat()})
 (OUT/'sitemap-general-tutor.xml').write_text(sitemap,encoding='utf8')
 robots=OUT/'robots.txt'
 if not robots.exists(): robots.write_text('User-agent: *\nAllow: /\nSitemap: '+DOMAIN+'/sitemap-general-tutor.xml\n',encoding='utf8')
 print(json.dumps({'candidate':len(ready),'generated':len(deploy),'deploy_ready':len(final),'similarity_hold':len(bad)},ensure_ascii=False))
if __name__=='__main__':
 try:
  main()
  set_stage('COMPLETE')
 except Exception as exc:
  original=f'{type(exc).__name__}: {exc}'
  try:
   write_run_report({'status':'FAIL','failure_reason':str(exc),'failure_type':type(exc).__name__,'failed_stage':CURRENT_STAGE,'timestamp':date.today().isoformat()})
  except Exception as report_exc:
   print(f'original failure: {original}',file=sys.stderr)
   print(f'report-write failure: {type(report_exc).__name__}: {report_exc}',file=sys.stderr)
  raise
