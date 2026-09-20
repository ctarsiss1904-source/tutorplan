"""Read-only navigation policy validation, including prospective in-memory HTML."""
from __future__ import annotations

import json
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

from navigation_parent import Navigation, ISOLATED, REVIEW_GROUP, RELATED


class Anchors(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.words = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.words = []

    def handle_data(self, data):
        if self.href is not None:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((''.join(self.words).strip(), self.href))
            self.href = None


def normalize(href):
    url = urlsplit(href)
    if url.netloc and url.netloc != 'tutorplan.co.kr':
        return None
    return unquote(url.path).rstrip('/') or '/' if url.path.startswith('/') else None


def validate(nav=None, prospective=None):
    nav = nav or Navigation()
    prospective = prospective or {}
    errors = Counter()
    summary = {}
    graph = {}
    related_inbound = Counter()
    directory_inbound = Counter()
    nav_counts = Counter()
    ready_routes = {p['route'].rstrip('/'): pid for pid, p in nav.pages.items()}
    isolated_route = nav.pages[ISOLATED]['route']
    fragments = 0
    scope = {s['page_id']: s for s in __import__('navigation_parent').csv_rows(nav.root / 'review/general_tutor_k_final_generation_scope.csv')}
    from generate_general_tutor_pages import render_k_content
    for path in nav.out.rglob('*.html'):
        text = prospective.get(path)
        if text is None:
            text = path.read_text(encoding='utf-8')
        route = '/' + path.relative_to(nav.out).as_posix()
        if route.endswith('/index.html'):
            route = route[:-11] or '/'
        route = route.rstrip('/') or '/'
        graph[route] = set()
        for label, href in Anchors(text).links:
            target = normalize(href)
            if target is None:
                continue
            graph[route].add(target)
            target_path = nav.out / target.lstrip('/')
            if not target_path.is_file() and not (target_path / 'index.html').is_file():
                errors['missing_html_all'] += 1
        pid = ready_routes.get(route)
        section = None
        mode = None
        if pid:
            mode = 'related'
            matches = RELATED.findall(text)
            if len(matches) != 1:
                errors['related_section'] += 1
                continue
            section = matches[0][1]
            actual = Anchors(section).links
            if actual != nav.related_targets(pid):
                errors['wrong_parent_navigation'] += 1
            fragment = re.search(r'<main><h1>.*?</h1>(.*?)<h2>관련 지역 과외</h2>', text, re.S)
            p = nav.pages[pid]
            raw = str(nav.source[(p['content_source_sheet'], int(p['content_source_row']))][10]).strip()
            expected = render_k_content(raw, scope[pid]['final_readiness'], pid)
            if not fragment or fragment[1] != expected:
                errors['k_fragment'] += 1
            fragments += 1
        elif path.is_relative_to(nav.out / 'regions'):
            mode = 'directory'
            group = REVIEW_GROUP if path == nav.out / 'regions/index.html' else path.parent.name
            pattern = r'<main class="wrap"><h1>.*?</h1>(.*?)</main>' if group == REVIEW_GROUP else r'<article class="card"><h1>.*?</h1>(.*?)</article>'
            found = re.search(pattern, text, re.S)
            if not found:
                errors['directory_section'] += 1
                continue
            section = found[1]
            if section != nav.directory_body(group):
                errors['directory_policy_mismatch'] += 1
        if mode:
            links = Anchors(section).links
            nav_counts[mode] += len(links)
            seen = set()
            for label, href in links:
                target = normalize(href)
                if not label:
                    errors['empty_anchor'] += 1
                if target in seen:
                    errors['duplicate_href'] += 1
                seen.add(target)
                if target == isolated_route or target == nav.directory(nav.pages[ISOLATED]['region_id']).rstrip('/'):
                    errors['isolated_target'] += 1
                if target and target.startswith('/tutor/') and target not in ready_routes:
                    errors['non_ready_target'] += 1
                if target in ready_routes:
                    (related_inbound if mode == 'related' else directory_inbound)[target] += 1
    seen = set()
    stack = ['/']
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, set()) - seen)
    unreachable = {pid for route, pid in ready_routes.items() if route not in seen}
    if unreachable != {ISOLATED}:
        errors['reachability'] += 1
    isolated_inbound = sum(isolated_route in targets for targets in graph.values())
    if isolated_inbound:
        errors['isolated_inbound'] += isolated_inbound
    def zero_counts(inbound):
        result = Counter()
        for route, pid in ready_routes.items():
            if not inbound[route]:
                result['total'] += 1
                result[nav.regions[nav.pages[pid]['region_id']]['region_level']] += 1
        return dict(result)
    evidence = Counter()
    regions = {}
    for sheet in ('대구', '대전', '인천', '광주'):
        ids = [pid for pid, p in nav.pages.items() if p['content_source_sheet'] == sheet and nav.regions[p['region_id']]['region_level'] == 'eupmyeondong']
        states = Counter(nav.records[pid]['status'] for pid in ids)
        evidence.update(states)
        grouping = Counter(nav.regions[nav.records[pid]['parent']]['display_name'] for pid in ids if nav.records[pid]['parent'])
        for pid in ids:
            record = nav.records[pid]
            if record['status'] == 'UNRESOLVED' and record['parent'] is not None:
                errors['unresolved_sigungu'] += 1
        regions[sheet] = {'total': len(ids), 'states': dict(states), 'grouping': dict(grouping), 'reachable': sum(nav.pages[pid]['route'] in seen for pid in ids)}
    if regions['대전']['grouping'] != {'동구':38,'중구':26,'서구':23,'유성구':45,'대덕구':25}:
        errors['daejeon_grouping'] += 1
    if evidence != Counter(TIER1_TIER2_CONFIRMED=152, TIER4_EXPLICIT=6, UNRESOLVED=551):
        errors['evidence_counts'] += 1
    # Independent coordinate expectations keep explicit evidence separate from confirmed review.
    for sheet, row, name in [('대전',87,'서구'),('대전',93,'유성구'),('대전',151,'대덕구'),('대전',152,'대덕구'),('대전',158,'대덕구'),('광주',108,'광산구')]:
        p = next(p for p in nav.pages.values() if p['content_source_sheet'] == sheet and int(p['content_source_row']) == row)
        record = nav.records[p['page_id']]
        if record['status'] != 'TIER4_EXPLICIT' or nav.regions[record['parent']]['display_name'] != name:
            errors['tier4_mismatch'] += 1
    summary.update(status='PASS' if not errors else 'FAIL', errors=dict(errors), related_anchors=nav_counts['related'], directory_anchors=nav_counts['directory'],
                   k_fragments_checked=fragments, evidence=dict(evidence), regions=regions, related_inbound0=zero_counts(related_inbound),
                   directory_inbound0=zero_counts(directory_inbound), combined_inbound0=zero_counts(related_inbound+directory_inbound),
                   ready=841, normal_ready=840, normal_reachable=840-len(unreachable-{ISOLATED}), unreachable=sorted(unreachable),
                   isolated_inbound=isolated_inbound, conflicts=len(nav.conflicts))
    return summary


if __name__ == '__main__':
    result = validate()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
