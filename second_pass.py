"""Classify the 133 non-confirmed parent proposals using stronger local evidence."""
from __future__ import annotations
import csv, json
from pathlib import Path
import build

def main():
    proposals=list(csv.DictReader((build.REVIEW/'parent_resolution_proposals.csv').open(encoding='utf-8-sig')))
    prior=[r for r in proposals if r['status']!='confirmed']
    official=next(Path(r'C:\Users\lovel\AppData\Local\Temp\legal-dong-source').glob('*.txt'))
    laws=list(csv.DictReader(official.open(encoding='cp949'),delimiter='\t'))
    aliases=__import__('resolve_parents').ALIASES
    records=[]; additions=[]
    for r in prior:
        sido=aliases[r['source_sheet']]; name=r['normalized_region_name']; raw=r['original_keyword'].replace(' ','')
        matches=[x['법정동명'].split() for x in laws if x['폐지여부']=='존재' and x['법정동명'].split()[0]==sido]
        direct=[p for p in matches if len(p)==2 and p[-1]==name]
        parents=sorted({' '.join(p[1:-1]) for p in matches if len(p)>=3 and p[-1]==name})
        explicit=[p for p in parents if ''.join(p) in raw or (r['source_sheet']+''.join(p)) in raw]
        evidence={'source_sheet_match':bool(direct or parents),'original_string_parent':bool(explicit),'neighbor_block_match':False,'same_sheet_pattern_match':False,'school_evidence_match':False,'official_reference_match':bool(direct or parents)}
        status='unresolved'; reason='insufficient_evidence'; parent=None; level=None; typ='unknown'; confidence='low'
        if direct:
            status='confirmed'; parent=r['source_sheet']; level='sido'; typ='administrative'; confidence='high'; reason=''; evidence['same_sheet_pattern_match']=True
        elif explicit and len(explicit)==1:
            status='confirmed'; parent=explicit[0]; level='sigungu'; typ='administrative'; confidence='high'; reason=''; evidence['neighbor_block_match']=True; evidence['same_sheet_pattern_match']=True
        elif len(parents)>1:
            status='manual_review'; reason='duplicate_name_same_sido'; typ='administrative'; confidence='medium'
        elif r['match_method']=='official_candidate_conflicts_with_source_sheet':
            status='suspected_bad_source_row'; reason='cross_sheet_conflict'; typ='unknown'; confidence='low'
        elif name.endswith(('시','군')):
            status='manual_review'; reason='missing_official_match'; typ='administrative'; confidence='medium'
        else:
            status='living_area' if r['source_sheet']=='제주도' else 'manual_review'; reason='living_area_not_official_region' if r['source_sheet']=='제주도' else 'missing_official_match'; typ='living_area' if status=='living_area' else 'unknown'
        row={**r,'normalized_name':name,'region_type':typ,'evidence':json.dumps(evidence,ensure_ascii=False),'confidence':confidence,'status':status,'unresolved_reason':reason,'reason':('Strong direct official match under the source-sheet jurisdiction.' if status=='confirmed' else r['reason']),'candidate_sigungu':parent if level=='sigungu' else '', 'candidate_parent':parent or ''}
        records.append(row)
        if status=='confirmed':
            additions.append({'source_sheet':r['source_sheet'],'source_row':int(r['source_row']),'candidate_parent':parent,'parent_level':level,'parent_region_id':build.slugify(r['source_sheet']) if level=='sido' else build.slugify(r['source_sheet'])+'-'+build.slugify(parent),'status':'confirmed'})
    fields=['source_sheet','source_row','original_keyword','normalized_name','candidate_sido','candidate_sigungu','candidate_parent','region_type','evidence','confidence','status','unresolved_reason','reason']
    def write(name,rows):
        with (build.REVIEW/name).open('w',newline='',encoding='utf-8-sig') as f: w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    write('parent_second_pass_all.csv',records)
    write('parent_second_pass_confirmed.csv',[x for x in records if x['status']=='confirmed'])
    write('parent_second_pass_manual_review.csv',[x for x in records if x['status']=='manual_review'])
    write('parent_second_pass_living_areas.csv',[x for x in records if x['status']=='living_area'])
    write('parent_second_pass_unresolved.csv',[x for x in records if x['status']=='unresolved'])
    write('suspected_bad_region_rows.csv',[x for x in records if x['status']=='suspected_bad_source_row'])
    payload=json.loads(build.PARENT_OVERRIDES.read_text(encoding='utf-8')); payload['records'].extend(additions); build.write_json(build.PARENT_OVERRIDES,payload)
    print({s:sum(x['status']==s for x in records) for s in ['confirmed','manual_review','living_area','suspected_bad_source_row','unresolved']})
if __name__=='__main__': main()
