from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PAGES = (
    "대구과외", "대전과외", "충북과외", "충남과외", "전북과외", "전남과외",
    "경북과외", "경남과외", "제주도과외",
    "수학과외", "영어과외", "국어과외", "과학과외", "초등과외", "중등과외", "고등과외",
)

TEMPLATE = """<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{title} | TutorPlan</title><meta name=\"description\" content=\"{title} 관련 과외 안내와 학습 정보를 확인하세요.\">
<style>body{{margin:0;background:#f5f7fa;color:#172235;font-family:\"Noto Sans KR\",Arial,sans-serif}}main{{width:min(760px,calc(100% - 40px));margin:18vh auto}}article{{padding:44px;background:#fff;border:1px solid #dce4ec;border-radius:18px}}h1{{margin:0;font-size:clamp(2rem,5vw,3rem)}}a{{display:inline-block;margin-top:26px;color:#176b87;text-decoration:none;font-weight:700}}</style></head>
<body><main><article><h1>{title}</h1><a href=\"/\">TutorPlan 홈으로</a></article></main></body></html>"""

for title in PAGES:
    directory = OUTPUT / title
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(TEMPLATE.format(title=title), encoding="utf-8")

print(f"Created {len(PAGES)} route placeholders in {OUTPUT}")
