import json, re
from pathlib import Path

ROOT=Path(__file__).parent
deploy=json.loads((ROOT/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'))
routes={x['canonical_url'].replace('https://tutorplan.co.kr','') for x in deploy if x['deploy_ready']}
canon=[]; titles=[]; h1s=[]; issues=[]; broken=0; links=0
for x in deploy:
    text=(ROOT/x['output_path']).read_text(encoding='utf8')
    canon += re.findall(r'<link rel="canonical" href="([^"]+)">',text)
    titles += re.findall(r'<title>(.*?)</title>',text)
    h1s += re.findall(r'<h1>(.*?)</h1>',text)
    if not all(token in text for token in ('<!doctype html>','<html lang="ko">','<head>','<body>','meta name="description"')) or len(re.findall(r'<h1>',text)) != 1:
        issues.append(x['page_id'])
    for target in re.findall(r'href="([^"]+)"',text):
        links += 1
        if target.startswith('/tutor/') and target not in routes: broken += 1
print(json.dumps({'pages':len(deploy),'html_issues':len(issues),'duplicate_canonical':len(canon)-len(set(canon)),'duplicate_title':len(titles)-len(set(titles)),'duplicate_h1':len(h1s)-len(set(h1s)),'broken_links':broken,'links':links},ensure_ascii=False))
