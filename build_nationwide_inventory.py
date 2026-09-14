"""Calculate nationwide SEO page candidates without rendering HTML or touching source data."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).parent
REGIONS = ROOT / "data/generated/regions.json"
SCHOOLS = ROOT / "data/generated/schools.json"
SOURCE = ROOT / "과외.xlsx"
RULES = ROOT / "data/config/page_combination_rules.json"
GENERATED = ROOT / "data/generated/nationwide_page_inventory_candidates.json"
REVIEW = ROOT / "review"
BASE_URL = "https://tutorplan.co.kr"
KOREAN = {
    "english": "영어", "math": "수학", "korean": "국어", "science": "과학",
    "elementary": "초등", "middle": "중등", "high": "고등",
    "elementary_school": "초등학교", "middle_school": "중학교", "high_school": "고등학교",
    "school_exam": "내신", "csat": "수능",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def slug_token(value: str) -> str:
    # Existing source IDs are collision-safe and stable; use them instead of transliteration.
    return value.replace("_", "-")


def content_sources():
    """Read F-K only; the workbook is opened read-only and never saved."""
    wb = load_workbook(SOURCE, read_only=True, data_only=True)
    values = {}
    for ws in wb.worksheets:
        for row_no, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            variables = {letter: bool(row[index]) if len(row) > index else False
                         for letter, index in zip("FGHIJK", range(5, 11))}
            values[(ws.title, row_no)] = {"variables": variables, "keyword": str(row[0] or "")}
    wb.close()
    return values


def title(region, subject=None, stage=None, school_type=None, exam=None, school=None):
    bits = [school or region["display_name"]]
    for value in (exam, stage, school_type, subject):
        if value:
            bits.append(KOREAN[value])
    return " ".join(bits) + "과외"


def route(region, page_type, subject=None, stage=None, school_type=None, exam=None, school=None):
    segments = ["tutor", region["region_id"], page_type]
    for value in (exam, stage, school_type, subject, school):
        if value:
            segments.append(slug_token(value))
    return "/" + "/".join(segments)


def region_content(region, source_values):
    key = (region["source_sheet"], region["source_row"])
    source = source_values.get(key, {"variables": {}})
    variables = source["variables"]
    return region["source_sheet"], region["source_row"], variables, "ready" if all(variables.values()) else "needs_content"


def build():
    rules = read_json(RULES)
    regions = [r for r in read_json(REGIONS) if r["is_source_region"]]
    schools = read_json(SCHOOLS)
    living = {(r["source_sheet"], int(r["source_row"])) for r in csv.DictReader(
        (REVIEW / "parent_second_pass_living_areas.csv").open(encoding="utf-8-sig"))}
    source_values = content_sources()
    by_region = {r["region_id"]: r for r in regions}
    candidates = []

    def add(page_type, region, *, subject=None, stage=None, school_type=None, exam=None, school=None, school_ref=None):
        src_sheet, src_row, variables, status = region_content(region, source_values)
        if school_ref:
            src_sheet, src_row = school_ref["source_sheet"], school_ref["source_row"]
            variables = source_values.get((src_sheet, src_row), {"variables": {}})["variables"]
            status = "pending_school_identity"
        page_route = route(region, page_type, subject, stage, school_type, exam,
                           school_ref.get("source_reference_id", school_ref["school_id"]) if school_ref else school)
        page_id = "candidate:" + page_route.strip("/").replace("/", ":")
        parent_id = None
        if school_ref:
            parent_id = None
        elif page_type != "region_tutor":
            parent_id = "candidate:" + route(region, "region_tutor").strip("/").replace("/", ":")
        elif region["parent_region_id"] in by_region:
            parent_id = "candidate:" + route(by_region[region["parent_region_id"]], "region_tutor").strip("/").replace("/", ":")
        candidates.append({
            "page_id": page_id, "page_type": page_type, "region_id": region["region_id"],
            "region_level": region["region_level"], "subject": subject, "student_stage": stage,
            "school_type": school_type, "exam_type": exam,
            "school_reference": None if not school_ref else {"source_reference_id": school_ref.get("source_reference_id"), "school_id": school_ref["school_id"], "display_name": school_ref["display_name"], "school_type": school_ref["school_type"]},
            "school_page_candidate": bool(school_ref), "title": title(region, subject, stage, school_type, exam, school),
            "slug": page_route.rsplit("/", 1)[-1], "canonical_url": BASE_URL + page_route,
            "route": page_route, "parent_page_id": parent_id, "content_source_sheet": src_sheet,
            "content_source_row": src_row, "content_variables_available": variables,
            "content_status": "available" if all(variables.values()) else "incomplete",
            "indexable_candidate": status == "ready", "status": status,
            "exclude_reason": None if status in ("ready", "needs_content", "pending_school_identity") else status,
        })

    for region in regions:
        level = "living_area" if (region["source_sheet"], region["source_row"]) in living else region["region_level"]
        region = dict(region, region_level=level)
        allowed = rules["region_level_page_types"].get(level, [])
        for pt in allowed:
            if pt == "region_tutor": add(pt, region)
            elif pt == "region_subject":
                for subject in rules["subjects"]: add(pt, region, subject=subject)
            elif pt == "region_stage":
                for stage in rules["student_stages"]: add(pt, region, stage=stage)
            elif pt == "region_stage_subject":
                for stage in rules["student_stages"]:
                    for subject in rules["subjects"]: add(pt, region, stage=stage, subject=subject)
            elif pt == "region_school_type":
                for school_type in rules["school_types"]: add(pt, region, school_type=school_type)
            elif pt == "region_school_type_subject":
                for school_type in rules["school_types"]:
                    for subject in rules["subjects"]: add(pt, region, school_type=school_type, subject=subject)
            elif pt == "region_exam":
                for exam in rules["exam_types"]: add(pt, region, exam=exam)
            elif pt == "region_exam_subject":
                for exam in rules["exam_types"]:
                    for subject in rules["subjects"]: add(pt, region, exam=exam, subject=subject)

    for school_index, raw_school in enumerate(schools, 1):
        school = dict(raw_school, source_reference_id=f"school-ref-{school_index}")
        region = by_region.get(school["school_id"].removeprefix("school-").rsplit("-", 1)[0])
        # School records are keyed by source region; use the first matching source coordinate safely.
        if not region:
            region = next((r for r in regions if r["source_sheet"] == school["source_sheet"] and r["source_row"] == school["source_row"]), None)
        if not region:
            source = source_values.get((school["source_sheet"], school["source_row"]), {})
            region = {
                "region_id": f"source-{school['source_sheet']}-{school['source_row']}",
                "display_name": source.get("keyword", school["source_sheet"]),
                "region_level": "eupmyeondong", "parent_region_id": None,
                "source_sheet": school["source_sheet"], "source_row": school["source_row"],
            }
        for subject in rules["subjects"]:
            add("school_subject", region, subject=subject, school=school["display_name"], school_ref=school)
            add("school_exam_subject", region, subject=subject, exam="school_exam", school=school["display_name"], school_ref=school)
    return candidates, rules


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def reviews(candidates, rules):
    fields = ["page_id", "page_type", "region_id", "region_level", "subject", "student_stage", "school_type", "exam_type", "school_reference", "title", "slug", "canonical_url", "parent_page_id", "content_source_sheet", "content_source_row", "content_variables_available", "content_status", "indexable_candidate", "status", "exclude_reason"]
    write_csv(REVIEW / "nationwide_page_inventory_candidates.csv", candidates, fields)
    canon = defaultdict(list); routes = defaultdict(list); slugs = defaultdict(list); titles = defaultdict(list); ids = {p["page_id"] for p in candidates}
    for p in candidates:
        canon[p["canonical_url"]].append(p); routes[p["route"]].append(p)
        slugs[(p["route"].rsplit("/", 1)[0], p["slug"])].append(p); titles[p["title"]].append(p)
    conflict_rows = []
    for kind, group in (("duplicate_canonical", canon), ("duplicate_route", routes), ("same_title_different_url", titles)):
        for value, pages in group.items():
            urls = {p["canonical_url"] for p in pages}
            if len(pages) > 1 and (kind != "same_title_different_url" or len(urls) > 1):
                for p in pages: conflict_rows.append({"conflict_type": kind, "value": value, "page_id": p["page_id"], "canonical_url": p["canonical_url"]})
    write_csv(REVIEW / "nationwide_route_conflicts.csv", conflict_rows, ["conflict_type", "value", "page_id", "canonical_url"])
    slug_rows = [{"parent_route": key[0], "slug": key[1], "page_id": p["page_id"], "canonical_url": p["canonical_url"]} for key, ps in slugs.items() if len(ps) > 1 for p in ps]
    write_csv(REVIEW / "nationwide_slug_conflicts.csv", slug_rows, ["parent_route", "slug", "page_id", "canonical_url"])
    invalid = []
    for p in candidates:
        if p["student_stage"] and p["exam_type"] and not rules["exam_stage_matrix"].get(f'{p["student_stage"]}:{p["exam_type"]}', False): invalid.append(p)
        if p["school_type"] and p["exam_type"] and not rules["school_type_exam_matrix"].get(f'{p["school_type"]}:{p["exam_type"]}', False): invalid.append(p)
    write_csv(REVIEW / "invalid_page_combinations.csv", invalid, fields)
    orphans = [p for p in candidates if p["parent_page_id"] and p["parent_page_id"] not in ids]
    write_csv(REVIEW / "orphan_page_candidates.csv", orphans, fields)
    pairs = [
        ("region_stage_subject", "region_school_type_subject", "중등 영어과외", "중학교 영어과외", "high", "학령 단계와 학교 유형의 대상·학교 정보·콘텐츠를 분리"),
        ("region_stage_subject", "region_school_type_subject", "고등 영어과외", "고등학교 영어과외", "high", "학령 단계와 특정 학교 유형의 탐색 의도를 분리"),
        ("region_exam_subject", "region_stage_subject", "내신 영어과외", "고등 내신 영어과외", "medium", "시험 중심 정보와 고등 학령 단계 맥락을 분리"),
    ]
    overlap = [{"page_type_a": a, "page_type_b": b, "example_title_a": f"강남구 {ta}", "example_title_b": f"강남구 {tb}", "overlap_risk": risk, "recommended_content_difference": rec} for a,b,ta,tb,risk,rec in pairs]
    write_csv(REVIEW / "search_intent_overlap.csv", overlap, list(overlap[0]))
    return {
        "duplicate_canonical": sum(len(ps) > 1 for ps in canon.values()),
        "duplicate_route": sum(len(ps) > 1 for ps in routes.values()),
        "same_title_multiple_url": sum(len({p["canonical_url"] for p in ps}) > 1 for ps in titles.values()),
        "slug_collision": sum(len(ps) > 1 for ps in slugs.values()),
        "orphan": len(orphans), "invalid": len(invalid), "overlap": len(overlap),
    }


def main():
    candidates, rules = build()
    GENERATED.parent.mkdir(parents=True, exist_ok=True)
    GENERATED.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = reviews(candidates, rules)
    summary = {"region_levels": Counter(p["region_level"] for p in candidates if not p["school_page_candidate"]), "page_types": Counter(p["page_type"] for p in candidates), "statuses": Counter(p["status"] for p in candidates), "region_based": sum(not p["school_page_candidate"] for p in candidates), "school_pending": sum(p["school_page_candidate"] for p in candidates), "total": len(candidates), "checks": checks}
    print(json.dumps(summary, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main()
