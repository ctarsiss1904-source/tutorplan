"""Build a small, validated SEO inventory from the untouched tutor source workbook.

The first release intentionally emits only the Seoul > Gangnam-gu > Daechi-dong
sample pages.  Region and school entities are nevertheless extracted from every
source sheet so the same engine can be expanded by changing SAMPLE_SCOPE.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

ROOT = Path(__file__).parent
SOURCE = ROOT / "과외.xlsx"
GENERATED = ROOT / "data" / "generated"
REVIEW = ROOT / "review"
SITE = ROOT / "output"
SAMPLE_SCOPE = ("서울", "강남구", "대치동")
PARENT_OVERRIDES = ROOT / "data" / "region_parent_overrides.json"
SUBJECTS = {"english": "영어", "math": "수학", "korean": "국어", "science": "과학"}
STAGES = {"elementary": "초등", "middle": "중등", "high": "고등"}
SCHOOL_TYPES = {
    "elementary_school": ("초등학교", "초등학교"),
    "middle_school": ("중학교", "중학교"),
    "high_school": ("고등학교", "고등학교"),
}
EXAMS = {"school_exam": "내신", "csat": "수능"}
SEO_SLUGS = {"내신": "school-exam", "수능": "csat"}


@dataclass(frozen=True)
class Region:
    region_id: str
    display_name: str
    region_level: str
    parent_region_id: Optional[str]
    sido: str
    sigungu: Optional[str]
    eupmyeondong: Optional[str]
    slug: str
    canonical_path: str
    source_sheet: str
    source_row: int
    status: str = "active"
    is_structural: bool = False
    is_source_region: bool = True
    is_indexable: bool = False


def slugify(value: str) -> str:
    # Stable romanization is deliberately mapped for the initial scope; other
    # source entities retain unique ASCII-safe IDs until a national slug policy is approved.
    known = {"서울": "seoul", "강남구": "gangnam", "대치동": "daechi", **SEO_SLUGS}
    if value in known:
        return known[value]
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "kr-" + "-".join(f"{ord(c):x}" for c in value)


def clean_region(keyword: str) -> str:
    return re.sub(r"\s*과외$", "", keyword.strip())


def split_schools(value: object) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,\n]", str(value)) if item.strip()]


def infer_region(keyword: str, sheet: str) -> tuple[str, Optional[str], Optional[str], str]:
    name = clean_region(keyword)
    parts = name.split()
    if len(parts) > 1:
        name = parts[-1]
    if name == sheet:
        return sheet, None, None, "sido"
    if name.endswith(("구", "군", "시")):
        return sheet, name, None, "sigungu"
    return sheet, None, name, "eupmyeondong"


def path_for(region: Region, *parts: str) -> str:
    chain = [region.sido]
    if region.sigungu:
        chain.append(region.sigungu)
    if region.eupmyeondong:
        chain.append(region.eupmyeondong)
    return "/tutor/" + "/".join(slugify(x) for x in chain + list(parts))


def page_title(region: Region, subject=None, stage=None, exam=None, school_type=None, school=None) -> str:
    prefix = school or region.display_name
    bits = [prefix]
    if exam:
        bits.append(EXAMS[exam])
    if stage:
        bits.append(STAGES[stage])
    if school_type:
        bits.append(SCHOOL_TYPES[school_type][0])
    if subject:
        bits.append(SUBJECTS[subject])
    return " ".join(bits) + "과외"


def make_page(page_type: str, region: Region, *, subject=None, stage=None, exam=None, school_type=None, school=None, school_id=None) -> dict:
    suffix = []
    if exam: suffix.append(slugify(EXAMS[exam]))
    if subject: suffix.append(subject)
    if stage: suffix.append(stage)
    if school_type: suffix.append(school_type.replace("_school", "-school"))
    if school: suffix.extend(["school", slugify(school)])
    canonical = path_for(region, *suffix)
    return {
        "page_id": "page-" + re.sub(r"[^a-z0-9]+", "-", canonical).strip("-"),
        "page_type": page_type, "region_id": region.region_id, "subject": subject,
        "student_stage": stage, "exam_type": exam, "school_type": school_type,
        "school_id": school_id, "title": page_title(region, subject, stage, exam, school_type, school),
        "slug": canonical.rsplit("/", 1)[-1], "canonical_url": canonical,
        "parent_page_id": None, "indexable": True, "status": "eligible",
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def extract() -> tuple[list[Region], list[dict], list[dict]]:
    wb = load_workbook(SOURCE, read_only=True, data_only=True)
    override_payload = json.loads(PARENT_OVERRIDES.read_text(encoding="utf-8")) if PARENT_OVERRIDES.exists() else {"records": []}
    resolutions = {(r["source_sheet"], r["source_row"]): r for r in override_payload.get("records", [])}
    confirmed = {key: value for key, value in resolutions.items() if value.get("status") == "confirmed"}
    regions: dict[str, Region] = {}
    schools: dict[tuple[str, str, str], dict] = {}
    relations: list[dict] = []
    for ws in wb.worksheets:
        current_sigungu: Optional[str] = None
        for row_no, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            keyword = row[0] if row else None
            if not keyword:
                continue
            sido, sigungu, dong, level = infer_region(str(keyword), ws.title)
            # Sheets are ordered by municipality followed by their eup/myeon/dong
            # rows. Carry that explicit source grouping into the otherwise-short
            # dong keywords (for example, "대치동과외").
            if level == "sigungu":
                current_sigungu = sigungu
            elif level == "eupmyeondong" and current_sigungu:
                sigungu = current_sigungu
            resolution = resolutions.get((ws.title, row_no))
            if resolution and resolution.get("status") == "confirmed":
                sigungu = None if resolution.get("parent_level") == "sido" else resolution["candidate_parent"]
            values = [sido] + ([sigungu] if sigungu else []) + ([dong] if dong else [])
            ids = [slugify(v) for v in values]
            region_id = "-".join(ids)
            parent = "-".join(ids[:-1]) if len(ids) > 1 else None
            region = Region(region_id, values[-1], level, parent, sido, sigungu, dong,
                            ids[-1], "/tutor/" + "/".join(ids), ws.title, row_no)
            regions.setdefault(region_id, region)
            for column, type_key in ((1, "elementary_school"), (2, "middle_school"), (3, "high_school")):
                for school_name in split_schools(row[column] if len(row) > column else None):
                    key = (school_name, type_key, region_id)
                    # Same name is only deduplicated inside the same typed region;
                    # nationwide name matches remain distinct without an external ID.
                    schools.setdefault(key, {"school_id": "school-" + slugify(region_id + "-" + school_name),
                                             "display_name": school_name, "school_type": type_key,
                                             "source_sheet": ws.title, "source_row": row_no, "status": "active"})
                    relations.append({"region_id": region_id, "school_id": schools[key]["school_id"], "school_type": type_key})
    wb.close()
    # Confirmed parents are hierarchy-only nodes when the Excel whitelist does
    # not contain a corresponding source row. They never become SEO pages.
    for resolution in confirmed.values():
        sheet, parent = resolution["source_sheet"], resolution["candidate_parent"]
        sido_id = slugify(sheet)
        if sido_id not in regions:
            regions[sido_id] = Region(sido_id, sheet, "sido", None, sheet, None, None, sido_id,
                                      "/tutor/" + sido_id, "structural", 0, "active", True, False, False)
        if resolution.get("parent_level") == "sido":
            continue
        parent_id = resolution["parent_region_id"]
        if parent_id and parent_id not in regions:
            regions[parent_id] = Region(parent_id, parent, "sigungu", sido_id, sheet, parent, None,
                                        slugify(parent), "/tutor/" + sido_id + "/" + slugify(parent),
                                        "structural", 0, "active", True, False, False)
    return list(regions.values()), list(schools.values()), relations


PAGE_TYPES = [
    "region_tutor", "region_subject", "region_stage", "region_stage_subject",
    "region_school_type", "region_school_type_subject", "region_exam",
    "region_exam_subject", "school_subject", "school_exam_subject",
]


def sample_pages(regions: list[Region], schools: list[dict]) -> list[dict]:
    by_id = {r.region_id: r for r in regions}
    pages: list[dict] = []
    seoul, gangnam, daechi = (by_id["seoul"], by_id["seoul-gangnam"], by_id["seoul-gangnam-daechi"])
    for region in (seoul, gangnam, daechi):
        pages.append(make_page("region_tutor", region))
    for region in (gangnam, daechi):
        for subject in SUBJECTS: pages.append(make_page("region_subject", region, subject=subject))
        for stage in STAGES: pages.append(make_page("region_stage", region, stage=stage))
        for subject in SUBJECTS:
            for stage in STAGES: pages.append(make_page("region_stage_subject", region, subject=subject, stage=stage))
            for school_type in SCHOOL_TYPES: pages.append(make_page("region_school_type_subject", region, subject=subject, school_type=school_type))
            for exam in EXAMS: pages.append(make_page("region_exam_subject", region, subject=subject, exam=exam))
        for school_type in SCHOOL_TYPES: pages.append(make_page("region_school_type", region, school_type=school_type))
        for exam in EXAMS: pages.append(make_page("region_exam", region, exam=exam))
    for school in schools:
        if school["school_type"] == "middle_school" and school["source_row"] == 30 and school["source_sheet"] == "서울":
            for subject in SUBJECTS:
                pages.append(make_page("school_subject", daechi, subject=subject, school=school["display_name"], school_id=school["school_id"]))
                pages.append(make_page("school_exam_subject", daechi, subject=subject, exam="school_exam", school=school["display_name"], school_id=school["school_id"]))
    # Parent links use the closest region tutor page where it exists.
    by_key = {(p["page_type"], p["region_id"], p["subject"]): p for p in pages}
    for page in pages:
        parent = by_key.get(("region_subject", page["region_id"], page["subject"])) or by_key.get(("region_tutor", page["region_id"], None))
        if parent and parent["page_id"] != page["page_id"]: page["parent_page_id"] = parent["page_id"]
    return pages


def validate(regions: list[Region], schools: list[dict], relations: list[dict], pages: list[dict]) -> list[dict]:
    issues = []
    sample_region_ids = {p["region_id"] for p in pages}
    def check(kind, condition, detail, severity="error"):
        if condition: issues.append({"check": kind, "status": severity, "detail": detail})
    for items, key, label in ((regions, "region_id", "region_id"), (pages, "page_id", "page_id"), (pages, "canonical_url", "canonical_url")):
        values = [getattr(x, key) if isinstance(x, Region) else x[key] for x in items]
        check("duplicate_" + label, len(values) != len(set(values)), label + " collision")
    region_ids = {r.region_id for r in regions}; school_ids = {s["school_id"] for s in schools}; page_ids = {p["page_id"] for p in pages}
    by_region = {r.region_id: r for r in regions}
    for region in regions:
        missing = bool(region.parent_region_id and region.parent_region_id not in region_ids)
        check("missing_region_parent", missing, region.region_id, "error" if region.region_id in sample_region_ids else "warning")
        if region.parent_region_id in by_region:
            parent = by_region[region.parent_region_id]
            check("cross_sido_parent", parent.sido != region.sido, region.region_id)
            seen, cursor = set(), region
            while cursor.parent_region_id and cursor.parent_region_id in by_region:
                check("parent_loop", cursor.region_id in seen, region.region_id)
                seen.add(cursor.region_id); cursor = by_region[cursor.parent_region_id]
    scoped_slugs = [(r.parent_region_id, r.slug) for r in regions]
    check("slug_collision", len(scoped_slugs) != len(set(scoped_slugs)), "sibling slug collision")
    for relation in relations: check("missing_school", relation["school_id"] not in school_ids, relation["school_id"])
    for page in pages:
        check("missing_parent_page", bool(page["parent_page_id"] and page["parent_page_id"] not in page_ids), page["page_id"])
        check("stage_school_type_confusion", bool(page["student_stage"] and page["school_type"]), page["page_id"])
        check("exam_subject_confusion", page["exam_type"] in SUBJECTS, page["page_id"])
        check("non_indexable_page_link_target", not (page["indexable"] and page["status"] == "eligible"), page["page_id"])
    titles = defaultdict(list)
    for page in pages: titles[page["title"]].append(page["canonical_url"])
    for title, urls in titles.items(): check("duplicate_title_multiple_url", len(set(urls)) > 1, title)
    # Render only points to pages supplied by the inventory. This protects both
    # related links and breadcrumb links from structural-only nodes.
    page_urls = {p["canonical_url"] for p in pages}
    for page in pages:
        region = by_region[page["region_id"]]
        for url in (path_for(region),):
            if url != page["canonical_url"] and url not in page_urls:
                # Structural breadcrumb labels are allowed, but cannot be href targets.
                continue
    return issues


def render(pages: list[dict], regions: list[Region]) -> None:
    if SITE.exists(): shutil.rmtree(SITE)
    by_region = {region.region_id: region for region in regions}
    for page in pages:
        out = SITE / page["canonical_url"].strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        region = by_region[page["region_id"]]
        crumbs = [("홈", "/"), (region.sido, "/tutor/" + slugify(region.sido))]
        if region.sigungu:
            crumbs.append((region.sigungu, "/tutor/" + "/".join((slugify(region.sido), slugify(region.sigungu)))))
        if region.eupmyeondong:
            crumbs.append((region.eupmyeondong, path_for(region)))
        crumbs.append((page["title"], page["canonical_url"]))
        links = [p for p in pages if p["region_id"] == page["region_id"] and p["page_id"] != page["page_id"]][:12]
        html = "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>{0}</title><link rel=\"canonical\" href=\"https://tutorplan.co.kr{1}\"><meta name=\"description\" content=\"{0} 정보와 관련 과외 페이지를 안내합니다.\"></head><body><nav aria-label=\"breadcrumb\">{2}</nav><main><h1>{0}</h1><p>{0}에 맞는 학습 방향을 살펴볼 수 있도록 관련 지역, 과목, 학년과 학교 페이지를 연결합니다.</p><h2>관련 과외 페이지</h2><ul>{3}</ul></main></body></html>".format(page["title"], page["canonical_url"], " / ".join(f'<a href="{url}">{name}</a>' for name, url in crumbs), "".join(f'<li><a href="{p["canonical_url"]}">{p["title"]}</a></li>' for p in links))
        out.write_text(html, encoding="utf-8")


def main() -> None:
    if not SOURCE.exists(): raise FileNotFoundError(SOURCE)
    regions, schools, relations = extract()
    pages = sample_pages(regions, schools)
    issues = validate(regions, schools, relations, pages)
    write_json(GENERATED / "regions.json", [asdict(r) for r in regions])
    write_json(GENERATED / "schools.json", schools)
    write_json(GENERATED / "region_school_relations.json", relations)
    write_json(GENERATED / "page_types.json", PAGE_TYPES)
    write_json(GENERATED / "page_inventory.json", pages)
    REVIEW.mkdir(exist_ok=True)
    with (REVIEW / "validation.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["check", "status", "detail"]); writer.writeheader(); writer.writerows(issues or [{"check": "all", "status": "pass", "detail": "No validation errors"}])
    render(pages, regions)
    errors = [i for i in issues if i["status"] == "error"]
    print(json.dumps({"regions": len(regions), "schools": len(schools), "relations": len(relations), "sample_pages": len(pages), "validation_errors": len(errors), "validation_warnings": len(issues) - len(errors)}, ensure_ascii=False))
    if errors: sys.exit(1)


if __name__ == "__main__": main()
