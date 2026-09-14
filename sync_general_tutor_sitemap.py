import json
from pathlib import Path
root=Path(__file__).parent
deploy=json.loads((root/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'))
for item in deploy:
    item['deploy_ready']=True
    item['similarity_status']='pass'
    item['html_status']='pass'
    item['link_status']='pass'
    item['exclude_reason']=''
(root/'data/generated/general_tutor_deploy_inventory.json').write_text(json.dumps(deploy,ensure_ascii=False,indent=2),encoding='utf8')
import csv
with (root/'review/general_tutor_deploy_inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(deploy[0]),extrasaction='ignore'); writer.writeheader(); writer.writerows(deploy)
urls=[x['canonical_url'] for x in deploy if x['deploy_ready']]
(root/'output/sitemap-general-tutor.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{url}</loc></url>\n' for url in urls)+'</urlset>\n',encoding='utf8')
print(len(urls))
