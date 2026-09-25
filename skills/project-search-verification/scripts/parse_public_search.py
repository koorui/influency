"""Normalize archived public-index responses without upgrading metadata to evidence."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def visible_text(value):
    parser = VisibleText()
    parser.feed(value)
    return '\n'.join(parser.parts)


def public_url(value):
    parsed = urlparse(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username and not parsed.password


def bing_target(value):
    parsed = urlparse(value)
    if parsed.hostname in ('bing.com', 'www.bing.com') and parsed.path == '/ck/a':
        encoded = parse_qs(parsed.query).get('u', [''])[0]
        if encoded.startswith('a1'):
            try:
                value = base64.urlsafe_b64decode(encoded[2:] + '=' * (-len(encoded[2:]) % 4)).decode('utf-8')
            except (ValueError, UnicodeError):
                return ''
    return value if public_url(value) else ''


class BingResults(HTMLParser):
    """Read only organic result headings; ignore ads, navigation and tracking links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_result = False
        self.in_heading = False
        self.active = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            self.in_result = 'b_algo' in attrs.get('class', '').split()
        if tag == 'h2' and self.in_result:
            self.in_heading = True
        if tag == 'a' and self.in_heading:
            self.active = {'url': bing_target(attrs.get('href', '')), 'title': ''}

    def handle_data(self, data):
        if self.active is not None:
            self.active['title'] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            if self.active['url']:
                self.items.append(self.active)
            self.active = None
        if tag == 'h2':
            self.in_heading = False
        if tag == 'li':
            self.in_result = False


def parse_items(channel, raw):
    if channel == 'bing':
        parser = BingResults()
        parser.feed(raw)
        return parser.items, 'organic_headings_only'
    data = json.loads(raw)
    if channel == 'crossref':
        works = data['message']['items'] if 'items' in data['message'] else [data['message']]
        return [{'title': ' '.join(x.get('title', [])), 'url': x.get('URL', ''),
                 'publisher': x.get('publisher', ''), 'doi': x.get('DOI'),
                 'date_metadata': {k: x[k] for k in ('published', 'published-online', 'published-print', 'created') if k in x},
                 'abstract': visible_text(x.get('abstract', '')),
                 'linked_urls': [v.get('URL') for v in x.get('link', []) if v.get('URL')],
                 'authors': x.get('author', [])}
                for x in works], 'parsed'
    if channel == 'openalex':
        return [{'title': x.get('display_name', ''), 'url': (x.get('primary_location') or {}).get('landing_page_url') or x.get('doi') or x.get('id', ''),
                 'doi': x.get('doi'), 'date_metadata': {'publication_date': x.get('publication_date')},
                 'linked_urls': [v for v in [(x.get('best_oa_location') or {}).get('pdf_url')] if v],
                 'authors': [v.get('author', {}).get('display_name') for v in x.get('authorships', [])]}
                for x in data['results']], 'parsed'
    if channel == 'github':
        if not isinstance(data,dict):raise ValueError('Unexpected GitHub response shape')
        repositories=data['items'] if 'items' in data else [data] if data.get('full_name') else []
        return [{'title': x.get('full_name', ''), 'url': x.get('html_url', ''),
                 'description': x.get('description'), 'owner': (x.get('owner') or {}).get('login'),
                 'date_metadata': {k: x.get(k) for k in ('created_at', 'updated_at', 'pushed_at')},
                 'current_stars': x.get('stargazers_count'), 'license': x.get('license'),
                 'historical_state_verified': False} for x in repositories], 'parsed'
    raise ValueError('Unsupported search channel')


def parse_archive(folder):
    folder = Path(folder).resolve()
    receipts = json.loads((folder / 'receipts.json').read_text(encoding='utf-8'))
    candidates, queries = [], []
    for receipt in receipts['queries']:
        query = {**receipt, 'candidate_ids': [], 'parse_status': 'access_failed'}
        if receipt['status'] == 'response_received':
            try:
                path = (folder / receipt['file']).resolve()
                if path.parent != folder:
                    raise ValueError('Receipt file must be inside its archive')
                raw = path.read_bytes()
                query['response_sha256'] = hashlib.sha256(raw).hexdigest()
                items, status = parse_items(receipt['channel'], raw.decode('utf-8-sig'))
                query['parse_status'] = status
                for n, item in enumerate(items, 1):
                    if not public_url(item['url']):
                        continue
                    identifier = f"{receipt['id']}-S{n:02d}"
                    candidates.append({**item, 'id': identifier, 'query_id': receipt['id'],
                                       'module': receipt['module'], 'access_status': 'metadata_only',
                                       'index_file': receipt['file'], 'index_sha256': query['response_sha256']})
                    query['candidate_ids'].append(identifier)
                # Zero parsed HTML headings can be a challenge page or layout change, not a negative search.
                if not query['candidate_ids'] and receipt['channel'] == 'bing':
                    query['parse_status'] = 'unparsed_or_no_organic_results'
            except (OSError, ValueError, KeyError, TypeError) as exc:
                query['parse_status'] = 'parse_failed'
                query['parse_error'] = str(exc)
        queries.append(query)
    return {'schema_version': 'public-search-candidates.v1', 'queries': queries, 'candidates': candidates,
            'boundary': '候选来源仅来自已归档检索响应；日期为索引元数据，尚未确认首次公开日或事件日。候选不代表对象匹配、全文核验或独立使用。'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = parse_archive(args.archive)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'queries': len(result['queries']), 'candidates': len(result['candidates']),
                      'parse_status': {q['id']: q['parse_status'] for q in result['queries']}}, ensure_ascii=False))
