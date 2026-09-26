"""Actual read-only public-index searches with durable raw responses.
Index metadata is never labelled as an opened paper or verified project performance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import re
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error

def crossref_url(query):
    doi=re.search(r'\b10\.\d{4,9}/[^\s"<>]+',query)
    if doi:
        return 'https://api.crossref.org/works/'+urllib.parse.quote(doi.group().rstrip('.,;'),safe='')
    return 'https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':query,'rows':10})


def github_url(query):
    repository=re.search(r'https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)',query)
    if repository:
        owner,name=repository.groups();name=name.removesuffix('.git')
        return f'https://api.github.com/repos/{owner}/{name}'
    return 'https://api.github.com/search/repositories?'+urllib.parse.urlencode({'q':query,'per_page':5})


CHANNELS={
    'crossref':crossref_url,
    'openalex':lambda q:'https://api.openalex.org/works?'+urllib.parse.urlencode({'search':q,'per-page':5}),
    'github':github_url,
    'bing':lambda q:'https://www.bing.com/search?'+urllib.parse.urlencode({'q':q}),
}

def collect(plan,output,*,id_offset=0):
    output.mkdir(parents=True,exist_ok=False)
    entries=plan['queries']
    if len(entries)>30:raise ValueError('最多30个有针对性的查询')
    def query(item):
        n,entry=item
        channel=entry['channel']
        if channel not in CHANNELS:raise ValueError('未知公共检索渠道')
        url=CHANNELS[channel](entry['query'])
        started=datetime.now(timezone.utc).isoformat()
        request=urllib.request.Request(url,headers={'User-Agent':'ImpactResearchAudit/1.0 (read-only evidence collection)','Accept':'application/json,text/html;q=0.9'})
        record={'id':f'Q{n:03d}','module':entry['module'],'query':entry['query'],'channel':channel,'url':url,'executed_at':started,'status':'access_failed'}
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                body=response.read(3*1024*1024+1)
                record['http_status']=response.status
                if len(body)>3*1024*1024:raise ValueError('检索响应超过3MB，未保存截断内容')
                ext='.json' if 'json' in response.headers.get('Content-Type','') else '.html'
                path=output/(record['id']+ext);path.write_bytes(body)
                record.update(status='response_received',file=path.name,bytes=len(body),content_type=response.headers.get('Content-Type',''))
        except Exception as exc:
            record['error']=str(exc)[:500]
            if isinstance(exc,urllib.error.HTTPError):record['http_status']=exc.code
        (output/(record['id']+'-receipt.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        return record
    with ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(query,enumerate(entries,1+id_offset)))
    result={'schema_version':'public-search-receipts.v1','new_requests_executed':len(records),
            'successful_responses':sum(r['status']=='response_received' for r in records),'queries':records,
            'boundary':'HTTP响应仅证明本次检索请求及所保存返回，不等于全文读取、独立证据或研究结论已核实。'}
    (output/'receipts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=collect(json.loads(a.plan.read_text(encoding='utf-8')),a.output)
    print(json.dumps({'requests':result['new_requests_executed'],'responses':result['successful_responses']},ensure_ascii=False))
