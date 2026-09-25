"""Collect two independently generated runs with verified upstream lineage.
Does not overwrite either run, change pipeline status, assign grades or publish reports.
"""
import argparse
import json
import shutil
import sys
import html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_store import fingerprint,atomic_json
from app.pipeline_v19 import wrapper


def collect(pipeline_root,v19_root,destination):
    state=json.loads((pipeline_root/'pipeline.json').read_text(encoding='utf-8'))
    def read_stage(name):
        entry=state['stages'][name]
        if entry['status']!='succeeded':raise ValueError(f'{name}未完成')
        value=json.loads((pipeline_root/entry['output']).read_text(encoding='utf-8'))
        if fingerprint(value)!=entry['output_hash']:raise ValueError('上游底稿已改变')
        return value
    intake=read_stage('wu_intake');search=read_stage('search_replay');attr=read_stage('attribution');wu=read_stage('wu_evaluation')
    workspace=json.loads((v19_root/'workspace.json').read_text(encoding='utf-8'))
    prov=workspace['pipeline_provenance']
    if (prov['intake_hash'],prov['search_hash'],prov['attribution_hash'])!=(fingerprint(intake),fingerprint(search['replay']),fingerprint(attr)):
        raise ValueError('v19不是基于本次输入生成，不能合并交付')
    v19=json.loads((v19_root/'artifacts/evaluation-run.json').read_text(encoding='utf-8'))
    checked=wrapper().validate_result(v19)
    if not checked['valid']:raise ValueError('v19尚未形成完整结果')
    destination.mkdir(parents=True,exist_ok=False)
    atomic_json(destination/'wu-evaluation.json',wu)
    atomic_json(destination/'v19-evaluation.json',v19)
    esc=lambda value:html.escape(str(value or ''))
    rows=''
    for outcome in v19.get('outcomes',[]):
        for d in outcome.get('dimensions',[]):
            grade=d.get('grade') or {}
            rows+=f'<tr><td>{esc(d.get("dimension_id"))}</td><td>{esc(grade.get("level"))}</td><td>{esc(d.get("conclusion"))}</td><td>{esc(grade.get("gap_to_next"))}</td></tr>'
    synthesis=v19.get('project_synthesis') or {}
    layers=''
    for key,label in [('specific_layer','特定层'),('global_layer','全局层'),('system_collaboration','协同判断')]:
        value=synthesis.get(key) or {}
        layers+=f'<section><h2>{label}</h2><p>{esc(value.get("status"))}</p><p>{esc(value.get("conclusion"))}</p></section>'
    level=synthesis.get('scope_impact_level') or {}
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>v19拉曼子成果评测底稿</title><style>body{font-family:system-ui,"Microsoft YaHei";max-width:1200px;margin:32px auto;padding:20px;color:#29465d;background:#f5f7fa;line-height:1.8}section{background:white;padding:20px;margin:16px 0;border:1px solid #dee7ef;border-radius:10px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border:1px solid #dde5ed;vertical-align:top}p,td{overflow-wrap:anywhere}.scroll{overflow:auto}.note{color:#9c642a}</style>'
    page+=f'<h1>v19 · 拉曼子成果评测底稿</h1><p class="note">真实模型运行结果，待人工审核。仅评价ACH-002，不代表全项目。v19等级与吴老师v2等级含义不同。</p><section><h2>本轮范围等级：{esc(level.get("level"))}</h2><p>{esc(level.get("reason"))}</p><p>{esc(level.get("scope"))}</p></section><section><h2>七维判断</h2><div class="scroll"><table><tr><th>维度</th><th>G级</th><th>结论</th><th>下一步证据</th></tr>{rows}</table></div></section>{layers}<section><h2>核对入口</h2><a href="v19-evaluation.json">完整v19 JSON</a> · <a href="wu-report/report.html">吴老师独立报告</a></section></html>'
    (destination/'v19-report.html').write_text(page,encoding='utf-8')
    wu_dir=pipeline_root/state['stages']['wu_evaluation']['output']
    shutil.copytree(wu_dir.parent/'artifacts',destination/'wu-report')
    atomic_json(destination/'attribution.json',attr)
    atomic_json(destination/'search-replay.json',search)
    atomic_json(destination/'manifest.json',{'test_type':'real-material-real-model','model':'gpt-6-astra','reasoning_effort':'medium',
        'wu_rubric':'wu-v2-six-levels','v19_rubric':'outcome-d1-d7-evaluation.v19',
        'pipeline_source':str(pipeline_root),'v19_source':str(v19_root),'lineage_verified':True,
        'wu_hash':fingerprint(wu),'v19_hash':fingerprint(v19),'published':False,
        'note':'跨阶段输出独立保存，等级数字不可直接比较；这是待人工审核的测试交付。'})
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pipeline',type=Path,required=True);p.add_argument('--v19',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(collect(a.pipeline.resolve(),a.v19.resolve(),a.output.resolve()))
