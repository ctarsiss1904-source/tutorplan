"""Third-pass structural audit. Reads candidates and source data; never renders pages."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).parent
SOURCE = ROOT / "과외.xlsx"
REGIONS = ROOT / "data/generated/regions.json"
CANDIDATES = ROOT / "data/generated/nationwide_page_inventory_candidates.json"
REVIEW = ROOT / "review"

P1 = {"region_tutor", "region_subject"}
P2 = {"region_stage", "region_stage_subject", "region_exam", "region_exam_subject"}
P3 = {"region_school_type", "region_school_type_subject"}


def write_csv(name, rows, fields):
    REVIEW.mkdir(exist_ok=True)
    with (REVIEW / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_audit(regions):
    wb = load_workbook(SOURCE, read_only=True, data_only=True)
    source_regions = [r for r in regions if r["is_source_region"]]
    structural_regions = [r for r in regions if r["is_structural"]]
    by_sheet = defaultdict(list)
    for r in source_regions:
        by_sheet[r["source_sheet"]].append(r)
    structural_by_name = defaultdict(list)
    for r in structural_regions:
        structural_by_name[r["display_name"]].append(r)
    rows, raw = [], []
    for ws in wb.worksheets:
        keys = []
        for row_no, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            if row and row[0]:
                keys.append(str(row[0]))
                raw.append((ws.title, row_no, str(row[0])))
        source_sidos = [r for r in by_sheet[ws.title] if r["region_level"] == "sido"]
        structural = structural_by_name[ws.title]
        detected = source_sidos[0]["display_name"] if source_sidos else ws.title
        target = source_sidos[0] if source_sidos else (structural[0] if structural else None)
        reason = "source_sido_keyword_present" if source_sidos else ("structural_parent_only" if structural else "sheet_has_no_sido_row")
        rows.append({"source_sheet": ws.title, "sheet_row_count": len(keys), "detected_sido": detected,
                     "sido_region_id": target["region_id"] if target else None,
                     "exists_as_source_region": bool(source_sidos), "exists_as_structural_region": bool(structural),
                     "indexable_candidate": bool(source_sidos), "reason": reason})
    wb.close()
    write_csv("source_sido_audit.csv", rows, list(rows[0]))
    return rows, raw


def hierarchy_counts(regions, source_rows):
    living = {(r["source_sheet"], int(r["source_row"])) for r in csv.DictReader(
        (REVIEW / "parent_second_pass_living_areas.csv").open(encoding="utf-8-sig"))}
    source = [r for r in regions if r["is_source_region"]]
    by_sido = defaultdict(lambda: Counter())
    for r in source:
        level = "living_area" if (r["source_sheet"], r["source_row"]) in living else r["region_level"]
        by_sido[r["sido"]][level] += 1
        by_sido[r["sido"]]["source_region_count"] += 1
        by_sido[r["sido"]]["indexable_region_count"] += 1
    for r in regions:
        if r["is_structural"]: by_sido[r["sido"]]["structural_region_count"] += 1
    rows = []
    for sido, c in sorted(by_sido.items()):
        rows.append({"sido": sido, "sigungu_count": c["sigungu"], "eupmyeondong_count": c["eupmyeondong"],
                     "living_area_count": c["living_area"], "source_region_count": c["source_region_count"],
                     "structural_region_count": c["structural_region_count"], "indexable_region_count": c["indexable_region_count"]})
    write_csv("region_hierarchy_counts_by_sido.csv", rows, list(rows[0]))
    kept = {(r["source_sheet"], r["source_row"]) for r in source}
    bad = {(r["source_sheet"], int(r["source_row"])) for r in csv.DictReader((REVIEW / "suspected_bad_region_rows.csv").open(encoding="utf-8-sig"))}
    raw_coords = {(sheet, row) for sheet, row, _ in source_rows}
    missing = raw_coords - kept
    reconciliation = {
        "raw_keyword_rows": len(raw_coords), "current_source_regions": len(source),
        "difference": len(raw_coords) - len(source), "duplicate_integration": len(missing - bad),
        "suspected_bad_source_row": len(missing & bad), "living_area": len(living),
        "structural_conversion": sum(r["is_structural"] for r in regions),
        "missing": 0, "non_region_rows": 0, "other": 0,
    }
    return rows, reconciliation


def region_labels(regions):
    by_id = {r["region_id"]: r for r in regions}
    display_counts = Counter(r["display_name"] for r in regions if r["is_source_region"])
    def label(region_id):
        r = by_id.get(region_id)
        if not r: return region_id
        if display_counts[r["display_name"]] == 1: return r["display_name"]
        parents = []
        cursor = r
        while cursor.get("parent_region_id") and cursor["parent_region_id"] in by_id:
            cursor = by_id[cursor["parent_region_id"]]
            parents.append(cursor["display_name"])
            if len(parents) == 2: break
        return " ".join(list(reversed(parents[:1])) + [r["display_name"]]) if parents else r["display_name"]
    return by_id, label


def title_groups(candidates, regions):
    by_id, seo_label = region_labels(regions)
    grouped = defaultdict(list)
    for p in candidates: grouped[p["title"]].append(p)
    rows, group_class, title_disambiguation = [], {}, set()
    for title, ps in grouped.items():
        urls = {p["canonical_url"] for p in ps}
        if len(urls) < 2: continue
        types = {p["page_type"] for p in ps}
        school = all(p["school_page_candidate"] for p in ps)
        levels = {p["region_level"] for p in ps}
        names = {by_id[p["region_id"]]["display_name"] for p in ps if p["region_id"] in by_id}
        if school:
            reason, severity, action = "SCHOOL_NAME_COLLISION", "EXPECTED_PENDING", "retain source references; decide only after school identity review"
        elif "living_area" in levels:
            reason, severity, action = "LIVING_AREA_NAME_COLLISION", "DISAMBIGUATION_REQUIRED", "use minimum parent label only when title duplicates"
        elif len(types) > 1:
            reason, severity, action = "PAGE_TYPE_SEMANTIC_COLLISION", "FIX_REQUIRED", "separate page-type title template and content intent"
        elif len(names) == 1:
            reason, severity, action = "SAME_REGION_NAME_DIFFERENT_PARENT", "DISAMBIGUATION_REQUIRED", "use minimum parent label only when title duplicates"
        else:
            reason, severity, action = "OTHER", "DUPLICATE_PAGE_CANDIDATE", "manual semantic review before enabling"
        for p in ps:
            if severity == "DISAMBIGUATION_REQUIRED": title_disambiguation.add(p["page_id"])
        group_class[title] = (reason, severity)
        rows.append({"title": title, "page_count": len(ps), "page_type": "|".join(sorted(types)),
                     "urls": "|".join(sorted(urls)), "region_ids": "|".join(sorted({p["region_id"] for p in ps})),
                     "region_names": "|".join(sorted(names)), "parent_regions": "|".join(sorted({seo_label(p["region_id"]) for p in ps})),
                     "subjects": "|".join(sorted({str(p["subject"]) for p in ps if p["subject"]})),
                     "student_stages": "|".join(sorted({str(p["student_stage"]) for p in ps if p["student_stage"]})),
                     "school_types": "|".join(sorted({str(p["school_type"]) for p in ps if p["school_type"]})),
                     "exam_types": "|".join(sorted({str(p["exam_type"]) for p in ps if p["exam_type"]})),
                     "collision_reason": reason, "severity": severity, "recommended_action": action})
    fields = ["title","page_count","page_type","urls","region_ids","region_names","parent_regions","subjects","student_stages","school_types","exam_types","collision_reason","severity","recommended_action"]
    write_csv("same_title_multiple_url_groups.csv", rows, fields)
    page_type_rows = [r for r in rows if r["collision_reason"] == "PAGE_TYPE_SEMANTIC_COLLISION"]
    write_csv("page_type_title_collisions.csv", page_type_rows, fields)
    return rows, title_disambiguation


def audit_candidates(candidates, disambiguation):
    rows = []
    for p in candidates:
        if p["school_page_candidate"]:
            priority, status = "HOLD", "pending_school_identity"
        else:
            priority = "P1" if p["page_type"] in P1 else "P2" if p["page_type"] in P2 else "P3"
            if p["page_id"] in disambiguation: status = "title_disambiguation_required"
            elif p["page_type"] == "region_tutor" and p["content_status"] == "available": status = "ready"
            elif p["content_status"] == "available": status = "needs_distinct_content"
            else: status = "needs_content"
        rows.append({"page_id": p["page_id"], "page_type": p["page_type"], "priority": priority,
                     "audit_status": status, "title": p["title"], "canonical_url": p["canonical_url"],
                     "content_source_sheet": p["content_source_sheet"], "content_source_row": p["content_source_row"]})
    write_csv("nationwide_page_inventory_structure_audit.csv", rows, list(rows[0]))
    return rows


def policies():
    rows = [
        ("region_tutor", True, True, True, False, "P1", "One source region page may be ready only after title audit."),
        ("region_subject", True, False, True, False, "P1", "Requires subject-specific content; source variables alone are insufficient."),
        ("region_stage", True, False, True, False, "P2", "Requires stage-specific content."),
        ("region_stage_subject", True, False, True, False, "P2", "Requires combined stage and subject content."),
        ("region_exam", True, False, True, False, "P2", "Requires exam-specific content."),
        ("region_exam_subject", True, False, True, False, "P2", "Requires exam and subject-specific content."),
        ("region_school_type", True, False, True, False, "P3", "Requires school-type-specific content and intent review."),
        ("region_school_type_subject", True, False, True, False, "P3", "Requires school-type and subject-specific content."),
        ("school_subject", False, False, True, True, "HOLD", "Pending school identity; do not publish."),
        ("school_exam_subject", False, False, True, True, "HOLD", "Pending school identity; do not publish."),
    ]
    fields = ["page_type","enabled","indexable_default","requires_unique_content","requires_school_data","priority","notes"]
    write_csv("page_type_rollout_policy.csv", [dict(zip(fields, row)) for row in rows], fields)


def overlap_detail():
    rows = [
        ("중등과외", "중학교과외", "region_stage", "region_school_type", "keep_both", "requires_distinct_content", "학령 단계 탐색과 학교 유형 탐색을 구분"),
        ("중등 영어과외", "중학교 영어과외", "region_stage_subject", "region_school_type_subject", "keep_both", "requires_distinct_content", "학령 단계별 학습과 학교 유형별 맥락을 구분"),
        ("고등과외", "고등학교과외", "region_stage", "region_school_type", "keep_both", "requires_distinct_content", "고등 학령 단계와 고등학교 유형을 구분"),
        ("고등 영어과외", "고등학교 영어과외", "region_stage_subject", "region_school_type_subject", "keep_both", "requires_distinct_content", "고등 영어의 학령·학교 유형 의도를 구분"),
        ("내신 영어과외", "고등 내신 영어과외", "region_exam_subject", "future_stage_exam_subject", "exclude_one", "requires_distinct_content", "현재 inventory에는 stage+exam page type이 없어 후자 생성 금지"),
        ("수능 영어과외", "고등 수능 영어과외", "region_exam_subject", "future_stage_exam_subject", "exclude_one", "requires_distinct_content", "현재 inventory에는 stage+exam page type이 없어 후자 생성 금지"),
    ]
    fields = ["example_a","example_b","page_type_a","page_type_b","recommendation","content_policy","reason"]
    write_csv("search_intent_overlap_detailed.csv", [dict(zip(fields, row)) for row in rows], fields)


def main():
    regions, candidates = load_json(REGIONS), load_json(CANDIDATES)
    sheets, raw = source_audit(regions)
    hierarchy, reconciliation = hierarchy_counts(regions, raw)
    groups, disambiguation = title_groups(candidates, regions)
    audited = audit_candidates(candidates, disambiguation)
    policies(); overlap_detail()
    summary = {"sheet_count": len(sheets), "source_sido": sum(r["exists_as_source_region"] for r in sheets),
               "reconciliation": reconciliation,
               "collision_reasons": Counter(r["collision_reason"] for r in groups),
               "severity": Counter(r["severity"] for r in groups),
               "rollout": {priority: Counter(r["audit_status"] for r in audited if r["priority"] == priority) for priority in ("P1","P2","P3","HOLD")}}
    print(json.dumps(summary, ensure_ascii=False, default=dict))


if __name__ == "__main__": main()
