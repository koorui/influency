"""CLI-operated evidence journal. Search choices belong to the CLI, not this helper."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from archive_public_sources import archive_sources

MODULES=['sota','prior_work','usage_media','github','indicator']


def native_items(path):
    seen=set()
    for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        item=event.get('item',{})
        if event.get('type')=='item.completed' and item.get('type')=='web_search' and item.get('id') not in seen:
            seen.add(item['id']);yield item


def sync_web(root,module):
    root=Path(root).resolve();journal=root/'research/journal.json'
    data=json.loads(journal.read_text(encoding='utf-8')) if journal.exists() else {
        'processed_web_calls':[],'search':{'queries':[],'candidates':[]},'primary_source_receipts':{'sources':[]},'selection':{'limitations':[]}}
    directory=root/'research/public-search';directory.mkdir(parents=True,exist_ok=True)
    for item in native_items(root/'events.jsonl'):
        if item['id'] in data['processed_web_calls']:continue
        data['processed_web_calls'].append(item['id'])
        action=item.get('action',{});terms=action.get('queries') or ([item.get('query')] if item.get('query') else [])
        if not terms:
            # Open results may reveal an additional canonical / alternate URL.
            if not data['search']['queries']:continue
            query=data['search']['queries'][-1]
        else:
            identifier=f"Q{len(data['search']['queries'])+1:03d}"
            filename=identifier+'.json';(directory/filename).write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
            query={'id':identifier,'module':module,'query':' | '.join(terms),'channel':'codex_web_search',
                'executed_at':datetime.now(timezone.utc).isoformat(),'status':'response_received','file':filename,
                'parse_status':'parsed','candidate_ids':[],'native_call_id':item['id']}
            data['search']['queries'].append(query)
        for result in item.get('results',[]):
            url=result.get('url','')
            if not url.startswith(('http://','https://')):continue
            if any(c['url']==url and c['query_id']==query['id'] for c in data['search']['candidates']):continue
            identifier=f"{query['id']}-S{len(query['candidate_ids'])+1:02d}"
            data['search']['candidates'].append({'id':identifier,'query_id':query['id'],'module':query['module'],
                'title':result.get('title',''),'url':url,'snippet':result.get('snippet',''),'native_ref_id':result.get('ref_id',''),
                'index_file':query['file'],'access_status':'metadata_only','native_call_id':item['id']})
            query['candidate_ids'].append(identifier)
    journal.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'receipts.json').write_text(json.dumps({'queries':data['search']['queries']},ensure_ascii=False,indent=2),encoding='utf-8')
    return data


def open_sources(root,ids):
    root=Path(root).resolve();journal=root/'research/journal.json';data=json.loads(journal.read_text(encoding='utf-8'))
    by_id={c['id']:c for c in data['search']['candidates']}
    if any(i not in by_id for i in ids):raise ValueError('Only URLs actually returned by native web search can be archived')
    previous={r['id'] for r in data['primary_source_receipts']['sources']}
    ids=[i for i in dict.fromkeys(ids) if i not in previous]
    if not ids:return data
    # A separate folder per CLI action preserves failed openings and retry history.
    output=root/'research'/f'open-{len(previous)+1:03d}'
    receipts=archive_sources([{'id':i,'url':by_id[i]['url']} for i in ids],output)
    primary=root/'research/primary-sources';primary.mkdir(exist_ok=True)
    import shutil
    for r in receipts['sources']:
        for key in ('raw_file','text_file'):
            if r.get(key):shutil.copyfile(output/r[key],primary/r[key])
        data['primary_source_receipts']['sources'].append(r)
    (primary/'receipts.json').write_text(json.dumps(data['primary_source_receipts'],ensure_ascii=False,indent=2),encoding='utf-8')
    journal.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data


def summary(data):
    opened={r['id']:r for r in data['primary_source_receipts']['sources']}
    return {'queries':len(data['search']['queries']),'modules':sorted({q['module'] for q in data['search']['queries']}),
        'sources':[{'id':c['id'],'title':c['title'],'url':c['url'],'opened':c['id'] in opened,
            'body_usable':opened.get(c['id'],{}).get('body_usable'),'text_chars':opened.get(c['id'],{}).get('text_chars'),
            'text_file':opened.get(c['id'],{}).get('text_file')} for c in data['search']['candidates']]}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('sync-web');s.add_argument('--module',choices=MODULES,required=True)
    o=sub.add_parser('open');o.add_argument('ids',nargs='+')
    sub.add_parser('status');a=p.parse_args()
    if a.command=='sync-web':data=sync_web(a.root,a.module)
    elif a.command=='open':data=open_sources(a.root,a.ids)
    else:data=json.loads((a.root/'research/journal.json').read_text(encoding='utf-8'))
    print(json.dumps(summary(data),ensure_ascii=False))
