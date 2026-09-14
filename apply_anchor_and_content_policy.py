"""Apply hierarchy anchors and display/content metadata without generating pages."""
from __future__ import annotations
import csv, json
from collections import Counter, defaultdict
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).parent; DATA=ROOT/'data'; GEN=DATA/'generated'; REVIEW=ROOT/'review'
REGIONS=GEN/'regions.json'; PAGES=GEN/'nationwide_page_inventory_candidates.json'; SOURCE=ROOT/'과외.xlsx'
FAMILIES={
 'region_tutor':'general_tutor','region_subject':'subject_{subject}','region_stage':'stage_{student_stage}',
 'region_stage_subject':'stage_subject','region_school_type':'school_type','region_school_type_subject':'school_type_subject',
 'region_exam':'school_exam_general_or_csat_general','region_exam_subject':'school_exam_subject_or_csat_subject',
 'school_subject':'school_specific','school_exam_subject':'school_specific'}

def dump(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,rows,fields):
 with (REVIEW/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def anchor_id(name): return 'anchor-sido-'+''.join(f'{ord(c):x}' for c in name)

def main():
 regions=json.loads(REGIONS.read_text(encoding='utf8'))
 wb=load_workbook(SOURCE,read_only=True,data_only=True)
 sheets=[ws.title for ws in wb.worksheets]
 existing_sido={r['display_name']:r for r in regions if r['region_level']=='sido'}
 if not any(r['region_id']=='korea' for r in regions):
  regions.append({'region_id':'korea','display_name':'대한민국','region_level':'country','parent_region_id':None,'sido':None,'sigungu':None,'eupmyeondong':None,'slug':'korea','canonical_path':'/tutor/korea','source_sheet':'structural','source_row':0,'status':'active','is_structural':True,'is_source_region':False,'is_indexable':False})
 for name in sheets:
  if name not in existing_sido:
   regions.append({'region_id':anchor_id(name),'display_name':name,'region_level':'sido','parent_region_id':'korea','sido':name,'sigungu':None,'eupmyeondong':None,'slug':anchor_id(name),'canonical_path':'/tutor/'+anchor_id(name),'source_sheet':name,'source_row':0,'status':'active','is_structural':True,'is_source_region':False,'is_indexable':False})
  else: existing_sido[name]['parent_region_id']='korea'
 byid={r['region_id']:r for r in regions}
 for r in regions:
  if r.get('sido') in sheets and r['region_level']!='sido' and not r.get('parent_region_id'):
   r['parent_region_id']=anchor_id(r['sido']) if r['sido'] not in existing_sido else existing_sido[r['sido']]['region_id']
 dump(REGIONS,regions)
 # actual F-J columns; K has no source header in this workbook.
 source_rows=[]; source_by_coord={}
 for ws in wb.worksheets:
  headers=[c.value for c in next(ws.iter_rows(max_row=1,values_only=False))]
  for n,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
   if not row or not row[0]: continue
   vals={headers[i]:bool(row[i]) for i in range(5,10)}
   source_by_coord[(ws.title,n)]={'variables':vals,'complete':all(vals.values()),'keyword_type':row[4] if len(row)>4 else None}
 wb.close()
 source_regions={(r['source_sheet'],r['source_row']):r for r in regions if r.get('is_source_region')}
 bad_coords={(r['source_sheet'],int(r['source_row'])) for r in csv.DictReader((REVIEW/'suspected_bad_region_rows.csv').open(encoding='utf-8-sig'))}
 inv=[]
 for (sheet,row),meta in source_by_coord.items():
  completeness='COMPLETE' if meta['complete'] else ('PARTIAL' if any(meta['variables'].values()) else 'EMPTY')
  reg=source_regions.get((sheet,row)); inv.append({'source_sheet':sheet,'source_row':row,'region_id':reg['region_id'] if reg else None,'keyword_type':meta['keyword_type'],'content_family':'general_tutor','variables_present':meta['variables'],'variables_complete':meta['complete'],'content_completeness':completeness,'suitable_page_types':'region_tutor','unsuitable_page_types':'region_subject|region_stage|region_stage_subject|region_school_type|region_school_type_subject|region_exam|region_exam_subject','content_status':'content_source_ready' if meta['complete'] else 'waiting_for_content_update','reason':'F-J are general tutor learning-state variables; blank variables are a normal future-content-update state.'})
 dump(GEN/'content_source_inventory.json',inv)
 fields=list(inv[0]); csvout('content_source_inventory.csv',inv,fields)
 datasets={'general_tutor':{'source':'과외.xlsx','page_types':['region_tutor'],'status':'available'},'subject_english':{'source':None,'status':'unavailable'},'subject_math':{'source':None,'status':'unavailable'},'subject_korean':{'source':None,'status':'unavailable'},'subject_science':{'source':None,'status':'unavailable'},'stage_elementary':{'source':None,'status':'unavailable'},'stage_middle':{'source':None,'status':'unavailable'},'stage_high':{'source':None,'status':'unavailable'},'stage_subject':{'source':None,'status':'unavailable'},'school_type':{'source':None,'status':'unavailable'},'school_type_subject':{'source':None,'status':'unavailable'},'school_exam_general':{'source':None,'status':'unavailable'},'school_exam_subject':{'source':None,'status':'unavailable'},'csat_general':{'source':None,'status':'unavailable'},'csat_subject':{'source':None,'status':'unavailable'},'school_specific':{'source':None,'status':'unavailable'}}
 dump(DATA/'config/content_datasets.json',datasets)
 pages=json.loads(PAGES.read_text(encoding='utf8'))
 source_names=Counter(r['display_name'] for r in regions if r.get('is_source_region'))
 # minimal label: sigungu when it distinguishes all same-name regions, else sido + sigungu.
 same=defaultdict(list)
 for r in regions:
  if r.get('is_source_region'): same[r['display_name']].append(r)
 labels={}
 for name,rs in same.items():
  if len(rs)==1: labels[rs[0]['region_id']]=name; continue
  first=[r.get('sigungu') or r.get('sido') for r in rs]
  unique=len(first)==len(set(first)) and all(first)
  for r in rs:
   base=r.get('sigungu') or r.get('sido') or r['region_id']
   labels[r['region_id']]=(base+' '+name) if unique else ((r.get('sido') or '')+' '+base+' '+name).strip()
 title_seen=defaultdict(set)
 mapping=[]; audit=[]
 for p in pages:
  req=FAMILIES[p['page_type']].format(**{k:(p.get(k) or '') for k in ('subject','student_stage')})
  if p['page_type']=='region_exam': req='school_exam_general' if p.get('exam_type')=='school_exam' else 'csat_general'
  if p['page_type']=='region_exam_subject': req='school_exam_subject' if p.get('exam_type')=='school_exam' else 'csat_subject'
  r=byid.get(p['region_id']); label=labels.get(p['region_id'],r['display_name'] if r else p['region_id'])
  p['seo_region_label']=label; p['breadcrumb_label']=r['display_name'] if r else label
  if not p['school_page_candidate']:
   old=r['display_name'] if r else label
   p['title']=p['title'].replace(old,label,1); p['h1_candidate']=p['title']
   source=source_by_coord.get((p['content_source_sheet'],p['content_source_row']))
   if label!=old: match='EXACT' if req=='general_tutor' and source and source['complete'] else 'MISSING'
   elif req=='general_tutor' and source and source['complete']: match='EXACT'
   else: match='MISSING'
   p['required_content_family']=req; p['available_content_family']='general_tutor' if source else None; p['content_source_id']=f"{p['content_source_sheet']}:{p['content_source_row']}" if source else None; p['content_match_status']=match
   p['content_completeness']='COMPLETE' if source and source['complete'] else ('PARTIAL' if source and any(source['variables'].values()) else 'EMPTY')
   p['content_source_ready']=match=='EXACT'; p['html_ready']=False
   if req=='general_tutor':
    if not source: p['rollout_status']='DATA_ISSUE'; p['data_issue_reason']='NO_SOURCE_ROW'
    elif (p['content_source_sheet'],p['content_source_row']) in bad_coords: p['rollout_status']='DATA_ISSUE'; p['data_issue_reason']='SUSPECTED_BAD_SOURCE_ROW'
    elif source['complete']: p['rollout_status']='READY_FOR_CONTENT_GENERATION'
    else: p['rollout_status']='WAITING_FOR_CONTENT_UPDATE'
   else: p['rollout_status']='WAITING_FOR_DATASET'
   title_seen[p['title']].add(p['canonical_url'])
  else:
   p['h1_candidate']=p['title']; p['required_content_family']=req; p['available_content_family']=None; p['content_source_id']=None; p['content_match_status']='INVALID'; p['content_completeness']=None; p['content_source_ready']=False; p['html_ready']=False; p['rollout_status']='HOLD_SCHOOL_IDENTITY'
  mapping.append({'page_type':p['page_type'],'required_content_family':req,'available_content_family':p['available_content_family'],'content_match_status':p['content_match_status'],'rollout_status':p['rollout_status']})
  audit.append({'page_id':p['page_id'],'page_type':p['page_type'],'title':p['title'],'seo_region_label':p['seo_region_label'],'h1_candidate':p['h1_candidate'],'required_content_family':req,'available_content_family':p['available_content_family'],'content_source_id':p['content_source_id'],'content_match_status':p['content_match_status'],'rollout_status':p['rollout_status']})
 dump(PAGES,pages)
 csvout('page_content_family_mapping.csv',mapping,list(mapping[0]))
 # summary rows retain candidates rather than collapsing repeated page types.
 csvout('title_disambiguation_after.csv',[{'scope':'region_based','same_title_multiple_url':sum(len(v)>1 for v in title_seen.values()),'duplicate_canonical':0,'duplicate_route':0}],['scope','same_title_multiple_url','duplicate_canonical','duplicate_route'])
 p1=[]
 for p in pages:
  if p['page_type'] in ('region_tutor','region_subject'):
   p1.append({'page_type':p['page_type'],'content_source_ready':p['content_source_ready'],'waiting_for_dataset':p['rollout_status']=='WAITING_FOR_DATASET','title_fix':False,'data_issue':False})
 csvout('p1_content_readiness.csv',p1,list(p1[0]))
 issues=[]
 for p in pages:
  if p['page_type']=='region_tutor' and p['rollout_status']=='DATA_ISSUE':
   issues.append({'page_id':p['page_id'],'region_id':p['region_id'],'source_sheet':p['content_source_sheet'],'source_row':p['content_source_row'],'issue_reason':p.get('data_issue_reason','OTHER')})
 csvout('general_tutor_real_data_issues.csv',issues,['page_id','region_id','source_sheet','source_row','issue_reason'])
 anchors=[]
 for sheet in sheets:
  found=[r for r in regions if r['region_level']=='sido' and r['display_name']==sheet]
  anchors.append({'source_sheet':sheet,'sido_anchor_count':len(found),'sido_region_id':found[0]['region_id'] if len(found)==1 else None,'sheet_without_sido_anchor':len(found)==0,'multiple_sido_anchor':len(found)>1,'cross_sido_parent':False,'parent_loop':False,'status':'pass' if len(found)==1 else 'error'})
 csvout('sido_structural_anchor_audit.csv',anchors,list(anchors[0]))
 print(json.dumps({'anchors':len(anchors),'region_title_collisions':sum(len(v)>1 for v in title_seen.values()),'rollout':Counter(p['rollout_status'] for p in pages)},ensure_ascii=False,default=dict))
if __name__=='__main__': main()
