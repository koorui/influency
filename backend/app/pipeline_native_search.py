"""CLI owns iterative live web research; host validates and publishes its evidence journal."""
import json
import shutil
from pathlib import Path
from pydantic import BaseModel,ConfigDict
from .pipeline_model import execute_json_stage
from .pipeline_store import atomic_json
from .search_skill_loader import SEARCH_SKILL_ROOT,contract


class ResearchCompletion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    summary:str
    limitations:list[str]
    completed_modules:list[str]


def collect_cli_research(payload,materials,folder):
    previous=find_research_checkpoint(payload,materials,folder)
    if previous:
        collected=read_cli_research(previous/'research-agent',folder)
        atomic_json(folder/'research-reuse.json',{'from_attempt':previous.name,'inputs_and_materials_matched':True})
        return collected
    agent=folder/'research-agent';agent.mkdir()
    (agent/'materials').mkdir()
    manifest=[]
    for n,m in enumerate(materials,1):
        relative=f'materials/{n:03d}.txt';(agent/relative).write_text(m['text'],encoding='utf-8')
        manifest.append({'id':m['id'],'filename':m['filename'],'text_file':relative})
    completion=execute_json_stage(agent,ResearchCompletion,{**payload,'materials':manifest},
        'You own the complete external Search investigation. Use native live web search extensively, then open primary results. '
        'Read the original materials and Search skill. Form and revise your own queries; do not stop at a fixed first round. '
        'Investigate all five modules separately: sota, prior_work, usage_media, github, indicator. '
        'After EACH module search batch, run python skill/scripts/research_session.py sync-web --module MODULE. '
        'This captures actual native web search event results and prints candidate IDs. '
        'Choose relevant candidate IDs yourself and run python skill/scripts/research_session.py open Q001-S01 ... to archive primary bodies. '
        'Read the archived text, assess relevance, and continue searching if a page is blocked, navigation-only, or off-topic. '
        'Use your native web open/find tools to discover accessible author manuscripts, publisher PDFs, institutional repositories, '
        'related methods and code; sync-web again to register returned URLs before archiving them. '
        'You may use Python/shell to inspect source files and write working notes in this directory, but do not edit the skill, '
        'events.jsonl, input.json, schema.json, or collected receipts. Never fabricate a search result or a successful opening. '
        'You have up to 30 minutes for careful research. Prefer depth and independent verification over cheap abbreviated output. '
        'No arbitrary positive evidence quota: honest scoped negative results are valid after meaningful varied searches. '
        'Do not relabel a cited base-model paper as adoption of this probe. Do not run repository code or contact anyone. '
        'Before completion, ensure journal covers all five modules and actual source bodies have been inspected where accessible. '
        'Return a concise completion summary; the host will assemble your raw journal for the final Search assessment.',
        skill_root=SEARCH_SKILL_ROOT,timeout=1800,live_search=True,inline_input=True,research_workspace=True)
    return read_cli_research(agent,folder)


def find_research_checkpoint(payload,materials,folder):
    """Reuse only completed research for the exact same inputs and full materials."""
    previous=sorted((p for p in folder.parent.glob('attempt-*') if p!=folder),
                    key=lambda p:int(p.name.split('-')[-1]),reverse=True)
    for attempt in previous:
        agent=attempt/'research-agent'
        try:
            saved=json.loads((agent/'input.json').read_text(encoding='utf-8'))
            manifest=saved.pop('materials')
            if saved!=payload or len(manifest)!=len(materials):continue
            matched=True
            for n,(entry,material) in enumerate(zip(manifest,materials),1):
                relative=f'materials/{n:03d}.txt'
                if entry!={'id':material['id'],'filename':material['filename'],'text_file':relative} or (agent/relative).read_bytes().decode('utf-8')!=material['text']:
                    matched=False;break
            if not matched:continue
            ResearchCompletion.model_validate_json((agent/'response.json').read_text(encoding='utf-8-sig'))
            if not (agent/'research/journal.json').is_file() or not (agent/'events.jsonl').is_file():continue
            return attempt
        except (OSError,ValueError,KeyError,TypeError):continue
    return None


def read_cli_research(agent,folder):
    completion=ResearchCompletion.model_validate_json((agent/'response.json').read_text(encoding='utf-8-sig'))
    journal=agent/'research/journal.json'
    if not journal.is_file():raise RuntimeError('CLI未保存实际检索记录，不能把文字总结当作已执行Search')
    collected=json.loads(journal.read_text(encoding='utf-8'))
    # Match collector claims to native tool events, rather than trusting self-reported calls.
    events=[]
    for line in (agent/'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if event.get('type')=='item.completed' and event.get('item',{}).get('type')=='web_search':events.append(event['item'])
    by_id={e['id']:e for e in events}
    if not any(e.get('action',{}).get('type')=='search' for e in events):
        raise RuntimeError('未记录到原生web search的实际调用')
    queries=collected['search']['queries']
    if {q['module'] for q in queries}!=contract.MODULES:raise RuntimeError('CLI检索记录未覆盖全部五模块')
    for q in queries:
        event=by_id.get(q.get('native_call_id'))
        if not event:raise ValueError('检索记录未对应原生工具调用')
        terms=event.get('action',{}).get('queries') or [event.get('query','')]
        if q['query']!=' | '.join(terms):raise ValueError('检索词与原生工具日志不一致')
    for c in collected['search']['candidates']:
        event=by_id.get(c.get('native_call_id'),{})
        if not any(r.get('url')==c['url'] for r in event.get('results',[])):
            raise ValueError('候选网址未出现在原生web search返回中')
    for name in ('public-search','primary-sources'):
        source=agent/'research'/name
        if source.exists():shutil.copytree(source,folder/name)
        else:(folder/name).mkdir()
    texts={}
    for receipt in collected['primary_source_receipts']['sources']:
        if receipt.get('text_file'):
            path=(folder/'primary-sources'/receipt['text_file']).resolve()
            if not path.is_relative_to((folder/'primary-sources').resolve()):raise ValueError('原文路径越界')
            texts[receipt['id']]=path.read_text(encoding='utf-8')
    collected['primary_source_texts']=texts;collected['selection']=completion.model_dump()
    collected['native_web_calls']=len(events)
    atomic_json(folder/'native-web-audit.json',{'calls':len(events),'queries':len(queries),'candidate_urls_verified':True})
    atomic_json(folder/'candidates.json',collected['search'])
    return collected
