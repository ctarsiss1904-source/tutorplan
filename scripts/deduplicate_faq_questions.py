from __future__ import annotations

import re
from collections import defaultdict
from html import unescape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "output"
REGIONS = ("서울과외", "인천과외", "광주과외", "부산과외", "울산과외", "세종과외", "경기도과외", "강원도과외")
FAQ_PATTERN = re.compile(r'(<section class="faq".*?</section>)', re.DOTALL)
QUESTION_PATTERN = re.compile(r"<h3>(.*?)</h3>")
FIRST_HEADING_PATTERN = re.compile(r'<section class="article">.*?<h2>(.*?)</h2>', re.DOTALL)


def clean(value: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(value)).strip()


def main() -> None:
    records = []
    for region in REGIONS:
        for path in sorted((ROOT / region).rglob("index.html")):
            html = path.read_text(encoding="utf-8")
            faq = FAQ_PATTERN.search(html)
            if not faq:
                continue
            heading = FIRST_HEADING_PATTERN.search(html)
            context = " / ".join(path.relative_to(ROOT).parts[:-1])
            focus = clean(heading.group(1)) if heading else "현재 학습 기록"
            for index, question in enumerate(QUESTION_PATTERN.findall(faq.group(1))):
                records.append((clean(question), path, index, context, focus))

    grouped = defaultdict(list)
    for record in records:
        grouped[record[0]].append(record)

    changed = 0
    for question, duplicates in grouped.items():
        for _, path, question_index, context, focus in duplicates[1:]:
            html = path.read_text(encoding="utf-8")
            faq = FAQ_PATTERN.search(html)
            assert faq
            questions = QUESTION_PATTERN.findall(faq.group(1))
            original = clean(questions[question_index])
            revised = f"‘{focus}’ 장면을 기준으로, {original}"
            questions[question_index] = revised
            iterator = iter(questions)
            revised_faq = QUESTION_PATTERN.sub(lambda _: f"<h3>{next(iterator)}</h3>", faq.group(1))
            path.write_text(html[: faq.start(1)] + revised_faq + html[faq.end(1) :], encoding="utf-8")
            changed += 1
    print(f"Revised {changed} duplicate FAQ questions.")


if __name__ == "__main__":
    main()
