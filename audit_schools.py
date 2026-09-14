"""Read-only school reference audit. It does not change generated entities."""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).parent; DATA=ROOT/'data'/'generated'; REVIEW=ROOT/'review'

def norm(value): return re.sub(r'\s+',' ',value.strip())
def write(name, rows, fields):
    with (REVIEW/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def main():
    regions={x['region_id']:x for x in json.loads((DATA/'regions.json').read_text(encoding='utf-8'))}
    schools={x['school_id']:x for x in json.loads((DATA/'schools.json').read_text(encoding='utf-8'))}
    relations=json.loads((DATA/'region_school_relations.json').read_text(encoding='utf-8'))
    living={(x['source_sheet'],x['source_row']) for x in csv.DictReader((REVIEW/'parent_second_pass_living_areas.csv').open(encoding='utf-8-sig'))}
    bad={(x['source_sheet'],x['source_row']) for x in csv.DictReader((REVIEW/'suspected_bad_region_rows.csv').open(encoding='utf-8-sig'))}
    refs=[]
    for rel in relations:
        school, region=schools[rel['school_id']], regions[rel['region_id']]
        flag='suspected_bad' if (region['source_sheet'],str(region['source_row'])) in bad else ('living_area' if (region['source_sheet'],str(region['source_row'])) in living else 'normal')
        refs.append({'source_sheet':school['source_sheet'],'source_row':school['source_row'],'region_id':region['region_id'],'region_name':region['display_name'],'school_name':school['display_name'],'normalized_school_name':norm(school['display_name']),'school_level':school['school_type'],'sido':region['sido'],'sigungu':region.get('sigungu') or '', 'source_region_status':flag,'relation_context':'living_area' if flag=='living_area' else 'source_reference'})
    fields=list(refs[0]); write('school_reference_inventory.csv',refs,fields)
    groups=defaultdict(list)
    for ref in refs: groups[(ref['normalized_school_name'],ref['school_level'])].append(ref)
    summaries=[]; buckets=defaultdict(list)
    for (name, level), rows in groups.items():
        region_ids={r['region_id'] for r in rows}; sidos={r['sido'] for r in rows}; sigungus={r['sigungu'] for r in rows}; levels={r['school_level'] for r in rows}
        cls='manual_review'; confidence='low'
        if len(sidos)>1: cls='DIFFERENT_SCHOOLS_SAME_NAME'; confidence='high'
        elif len(region_ids)>1 and len(sigungus)==1: cls='SAME_SCHOOL_MULTI_REGION_REFERENCE_CANDIDATE'; confidence='medium'
        elif len(region_ids)>1 and len(sigungus)>1: cls='nearby_school_candidate'; confidence='low'
        summary={'normalized_school_name':name,'school_level':level,'reference_count':len(rows),'region_count':len(region_ids),'sigungu_count':len(sigungus),'sido_count':len(sidos),'classification':cls,'confidence':confidence,'source_region_statuses':','.join(sorted({r['source_region_status'] for r in rows}))}
        if len(rows)>1: summaries.append(summary); buckets[cls].append(summary)
    # Name-level school-grade collision needs a separate comparison.
    name_levels=defaultdict(set)
    for name, level in groups: name_levels[name].add(level)
    mismatches=[]
    for name, levels in name_levels.items():
        if len(levels)>1: mismatches.append({'normalized_school_name':name,'school_levels':','.join(sorted(levels)),'classification':'SUSPECTED_MISMATCH','confidence':'medium','reason':'Same normalized name appears with more than one Excel school-level column.'})
    summary_fields=['normalized_school_name','school_level','reference_count','region_count','sigungu_count','sido_count','classification','confidence','source_region_statuses']
    write('school_name_collision_groups.csv',summaries,summary_fields)
    write('same_school_multi_region_candidates.csv',buckets['SAME_SCHOOL_MULTI_REGION_REFERENCE_CANDIDATE'],summary_fields)
    write('different_schools_same_name.csv',buckets['DIFFERENT_SCHOOLS_SAME_NAME'],summary_fields)
    write('nearby_school_candidates.csv',buckets['nearby_school_candidate'],summary_fields)
    write('suspected_school_mismatches.csv',mismatches,list(mismatches[0]) if mismatches else ['normalized_school_name','school_levels','classification','confidence','reason'])
    write('school_manual_review.csv',buckets['manual_review'],summary_fields)
    (REVIEW/'school_model_recommendation.md').write_text('''# School model recommendation\n\nKeep the current provisional `school_id` unchanged during this audit. Add `normalized_school_name`, `school_level`, `canonical_school_key`, `official_school_code`, `official_address`, and `source_count` in a later migration. `official_school_code` must become the preferred key only after an authoritative match. Preserve every Excel relation with `relation_type: source_reference` by default; use `living_area_reference` only for rows already classified as living areas. Do not infer a school address or convert a reference into `in_region`.\n''',encoding='utf-8')
    print(json.dumps({'references':len(refs),'unique_names':len({r['normalized_school_name'] for r in refs}),'collision_groups':len(summaries),'same':len(buckets['SAME_SCHOOL_MULTI_REGION_REFERENCE_CANDIDATE']),'different':len(buckets['DIFFERENT_SCHOOLS_SAME_NAME']),'nearby':len(buckets['nearby_school_candidate']),'mismatch':len(mismatches),'manual':len(buckets['manual_review'])},ensure_ascii=False))
if __name__=='__main__': main()
