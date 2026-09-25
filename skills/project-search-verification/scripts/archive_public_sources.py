"""Archive selected HTTP sources and extracted text; never assert scientific verification."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import urllib.request
from urllib.parse import urlparse
from parse_public_search import visible_text

LIMIT = 12 * 1024 * 1024


def check_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only unauthenticated public HTTP(S) sources are allowed')
    if parsed.port not in (None, 80, 443):
        raise ValueError('Nonstandard source port')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Source resolves to a non-public address')


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def archive_sources(selections, output):
    output = Path(output)
    if len(selections) > 30:
        raise ValueError('At most 30 selected primary sources per pass')
    identifiers = [item['id'] for item in selections]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate source selection ID')
    for identifier in identifiers:
        if not identifier or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in identifier):
            raise ValueError('Invalid archive ID')
    output.mkdir(parents=True, exist_ok=False)

    def fetch(item):
        identifier, url = item['id'], item['url']
        record = {'id': identifier, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                  'status': 'access_failed', 'access_status': 'blocked'}
        try:
            check_public_url(url)
            # Do not inherit authenticated application clients or forward credentials.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicRedirect())
            request = urllib.request.Request(url, headers={'User-Agent': 'ImpactResearchAudit/1.0', 'Accept': 'text/html,application/pdf,application/json,text/plain;q=0.9'})
            with opener.open(request, timeout=25) as response:
                body = response.read(LIMIT + 1)
                record.update(final_url=response.url, http_status=response.status,
                              content_type=response.headers.get('Content-Type', ''))
                if len(body) > LIMIT:
                    raise ValueError('Source exceeds 12 MB; no truncated content accepted')
                charset = response.headers.get_content_charset() or 'utf-8'
            raw_path = output / (identifier + '.raw')
            raw_path.write_bytes(body)
            record.update(status='response_archived', raw_file=raw_path.name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            if body.startswith(b'%PDF'):
                from pypdf import PdfReader
                reader = PdfReader(raw_path)
                if len(reader.pages) > 1000:
                    raise ValueError('PDF exceeds 1000 pages')
                text = '\n\n'.join(f'[physical page {n}]\n{page.extract_text() or ""}' for n, page in enumerate(reader.pages, 1))
            elif 'html' in record['content_type']:
                text = visible_text(body.decode(charset, errors='replace'))
            elif 'json' in record['content_type'] or record['content_type'].startswith('text/'):
                text = body.decode(charset, errors='replace')
            else:
                raise ValueError('Unsupported text extraction content type')
            text_path = output / (identifier + '.txt')
            text_path.write_text(text, encoding='utf-8')
            record.update(text_file=text_path.name, text_chars=len(text), text_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                          access_status='metadata_only', status='text_extracted',
                          boundary='Extracted response text may be an abstract, login/challenge page or partial article. A reader must verify body coverage before claiming full text.')
        except Exception as exc:
            record['error'] = str(exc)[:500]
        (output / (identifier + '-receipt.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        return record

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(fetch, selections))
    result = {'schema_version': 'public-source-archive.v1', 'sources': records}
    (output / 'receipts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selections', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = archive_sources(json.loads(args.selections.read_text(encoding='utf-8')), args.output)
    print(json.dumps([{'id': r['id'], 'status': r['status'], 'chars': r.get('text_chars'), 'error': r.get('error')} for r in result['sources']], ensure_ascii=False))
