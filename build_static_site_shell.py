"""Build non-content static site shell and region directories from Python inventories."""
from __future__ import annotations
import json,re
from collections import defaultdict
from pathlib import Path
from jinja2 import Environment, BaseLoader, select_autoescape

ROOT=Path(__file__).parent; OUT=ROOT/'output'; DOMAIN='https://tutorplan.co.kr'
env=Environment(loader=BaseLoader(),autoescape=select_autoescape(['html']))
BASE='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ title }}</title><meta name="description" content="{{ description }}"><link rel="canonical" href="{{ canonical }}"><meta name="robots" content="index,follow"><style>body{margin:0;font-family:Arial,'Noto Sans KR',sans-serif;color:#152238;background:#f6f9fc;line-height:1.7}.wrap{max-width:1050px;margin:auto;padding:0 20px}header,footer{background:#fff;border-color:#dce4ec;border-style:solid}header{border-width:0 0 1px}footer{border-width:1px 0 0;margin-top:48px}.bar{display:flex;justify-content:space-between;gap:16px;padding:16px 0}.brand{font-weight:800;color:#10314b;font-size:1.25rem}a{color:#0d5f7a;text-decoration:none}a:hover{text-decoration:underline}nav a{margin-left:16px}main{min-height:68vh;padding:42px 0}.card{background:#fff;border:1px solid #dce4ec;border-radius:12px;padding:20px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.crumb{font-size:.9rem;color:#5b6878}.crumb span{margin:0 6px}.hero{background:#10314b;color:#fff;border-radius:16px;padding:42px}.hero a{color:#bfe9f5}h1{line-height:1.25}ul{padding-left:20px}@media(max-width:640px){.bar{flex-direction:column}nav a{margin:0 14px 0 0}}</style></head><body><header><div class="wrap bar"><a class="brand" href="/">TutorPlan</a><nav><a href="/regions/">지역 찾기</a><a href="/tutoring/">학습관리</a><a href="/contact/">문의</a></nav></div></header><main class="wrap">{% block body %}{% endblock %}</main><footer><div class="wrap bar"><span>TutorPlan</span><span><a href="/privacy/">개인정보처리방침</a> · <a href="/terms/">이용약관</a></span></div></footer></body></html>'''
def render(body,**ctx): return env.from_string('{% extends base %}{% block body %}'+body+'{% endblock %}').render(base=env.from_string(BASE),**ctx)
def write(route,text):
 p=OUT/route.strip('/')/'index.html' if route!='/' else OUT/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
def main():
 deploy=json.loads((ROOT/'data/generated/general_tutor_deploy_inventory.json').read_text(encoding='utf8'));ready=[x for x in deploy if x['deploy_ready']]
 regions=json.loads((ROOT/'data/generated/regions.json').read_text(encoding='utf8'));byid={r['region_id']:r for r in regions};children=defaultdict(list)
 for r in regions:
  if r.get('parent_region_id') in byid:children[r['parent_region_id']].append(r)
 tutor={x['region_id']:x for x in ready}
 home='''<section class="hero"><h1>지역의 학습 흐름을 살피는 과외</h1><p>현재 콘텐츠 준비가 완료된 지역별 일반 과외 페이지를 탐색할 수 있습니다.</p><a href="/regions/">지역별 과외 찾기</a></section><section><h2>안내</h2><div class="grid"><div class="card"><h3>지역별 탐색</h3><p>시도부터 생활권까지 현재 공개 가능한 지역을 확인합니다.</p><a href="/regions/">지역 찾기</a></div><div class="card"><h3>학습관리</h3><p>현재 상태와 실제 행동을 바탕으로 학습 흐름을 정리합니다.</p><a href="/tutoring/">학습관리 안내</a></div></div></section>'''
 write('/',render(home,title='TutorPlan',description='지역별 학습관리와 과외 정보를 안내합니다.',canonical=DOMAIN+'/'))
 common={'/tutoring/':('과외·학습관리 안내','현재 상태, 실제 행동, 원인, 개선 기준을 함께 살피는 과외 학습관리 안내입니다.','<article class="card"><h1>과외·학습관리 안내</h1><p>과외는 단순한 진도 확인보다 현재 학습 흐름을 이해하고 다음 행동을 정하는 과정입니다.</p><h2>학습 흐름 기록</h2><p>수업 전후의 행동과 변화 기준을 기록하면 다음 회차의 계획을 구체화할 수 있습니다.</p></article>'),'/contact/':('문의','TutorPlan 문의 안내입니다.','<article class="card"><h1>문의</h1><p>현재 학습 상황과 확인하고 싶은 변화를 정리한 뒤 문의해 주세요.</p><p>연락 채널과 운영 정보는 실제 서비스 운영 시 확정하여 안내합니다.</p></article>'),'/privacy/':('개인정보처리방침','TutorPlan 개인정보처리방침 안내입니다.','<article class="card"><h1>개인정보처리방침</h1><p>TODO: 실제 서비스 운영 주체, 수집 항목, 보관 기간 및 문의처 확정 후 게시합니다.</p></article>'),'/terms/':('이용약관','TutorPlan 이용약관 안내입니다.','<article class="card"><h1>이용약관</h1><p>TODO: 실제 서비스 운영 정책과 사업자 정보 확정 후 게시합니다.</p></article>')}
 for route,(title,desc,body) in common.items():write(route,render(body,title=title,description=desc,canonical=DOMAIN+route))
 root_nodes=[r for r in regions if r['region_level']=='sido'];cards=[]
 for r in sorted(root_nodes,key=lambda x:x['display_name']):
  link='/regions/'+r['region_id']+'/';t=tutor.get(r['region_id']);name=r['display_name'];cards.append(f'<article class="card"><h2><a href="{link}">{name}</a></h2>'+ (f'<p><a href="{t["canonical_url"].replace(DOMAIN,"")}">{name}과외 보기</a></p>' if t else '<p>현재 준비 중인 지역입니다.</p>')+'</article>')
 write('/regions/',render('<h1>지역별 과외 찾기</h1><p>콘텐츠 준비가 완료된 지역만 과외 상세 페이지로 연결합니다.</p><div class="grid">'+''.join(cards)+'</div>',title='지역별 과외 찾기',description='시도, 시군구, 읍면동과 생활권별 현재 공개 가능한 과외 페이지를 찾습니다.',canonical=DOMAIN+'/regions/'))
 directory_count=0
 for r in regions:
  route='/regions/'+r['region_id']+'/'; parent=byid.get(r.get('parent_region_id')); child=sorted(children.get(r['region_id'],[]),key=lambda x:x['display_name']);t=tutor.get(r['region_id'])
  crumbs='<a href="/">홈</a><span>›</span><a href="/regions/">지역 찾기</a>'+(f'<span>›</span><a href="/regions/{parent["region_id"]}/">{parent["display_name"]}</a>' if parent and parent['region_level']!='country' else '')+f'<span>›</span>{r["display_name"]}'
  target=f'<p><a href="{t["canonical_url"].replace(DOMAIN,"")}">{r["display_name"]}과외 보기</a></p>' if t else '<p>이 지역의 과외 상세 페이지는 현재 콘텐츠 준비 중입니다.</p>'
  listing=''.join(f'<li><a href="/regions/{c["region_id"]}/">{c["display_name"]}</a>'+ (f' · <a href="{tutor[c["region_id"]]["canonical_url"].replace(DOMAIN,"")}">과외</a>' if c['region_id'] in tutor else '')+'</li>' for c in child)
  body=f'<nav class="crumb">{crumbs}</nav><article class="card"><h1>{r["display_name"]} 지역 탐색</h1>{target}<h2>하위 지역</h2><ul>{listing or "<li>하위 지역 정보가 없습니다.</li>"}</ul></article>'
  write(route,render(body,title=r['display_name']+' 지역 찾기',description=r['display_name']+' 지역의 현재 공개 가능한 과외 페이지를 탐색합니다.',canonical=DOMAIN+route));directory_count+=1
 notfound='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>페이지를 찾을 수 없습니다 | TutorPlan</title></head><body><h1>페이지를 찾을 수 없습니다</h1><p>준비되지 않았거나 존재하지 않는 주소입니다.</p><a href="/">홈으로 돌아가기</a></body></html>''';(OUT/'404.html').write_text(notfound,encoding='utf8')
 sitemap='<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <sitemap><loc>'+DOMAIN+'/sitemap-general-tutor.xml</loc></sitemap>\n</sitemapindex>\n';(OUT/'sitemap.xml').write_text(sitemap,encoding='utf8')
 (OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+DOMAIN+'/sitemap.xml\n',encoding='utf8')
 print(json.dumps({'ready':len(ready),'directories':directory_count,'common':6},ensure_ascii=False))
if __name__=='__main__':main()
