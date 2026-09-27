import argparse
import html
import json
from pathlib import Path
from assessment_contract import Assessment


def export_artifacts(value: Assessment, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    data=value.model_dump()
    for name,item in [('evaluation-result',data),('outcome-resolution',data['outcome_resolution']),('outcome-card',data['outcome_card']),('evidence-ledger',{'evidence':data['evidence_index'],'claims':data['claims'],'dimensions':data['dimensions'],'ai_attribution':data['ai_attribution']})]:
        (output/f'{name}.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
    if value.fact_ledger:
        for name,item in [('claim-ledger',value.fact_ledger.model_dump()['claims']),('fact-ledger',value.fact_ledger.model_dump())]:
            (output/f'{name}.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
    esc=lambda s:html.escape(str(s or ''))
    evidence={e.id:e for e in value.evidence_index}
    refs=lambda ids:' '.join(f'<a href="#e-{esc(i)}">{esc(evidence[i].title)}</a>' for i in ids)
    reasons=''.join(f'<li>{esc(r.text)} {refs(r.evidence_ids)}</li>' for r in value.level_reasons)
    rows=''.join(f'<tr><th>{esc(j.topic)}</th><td>{esc(j.project_claim)}<p>{refs(j.project_evidence_ids)}</p></td><td>{esc(j.assessment)}<p>{refs(j.evaluation_evidence_ids)}</p></td></tr>' for j in value.key_judgments)
    evidence_html=''.join(f'<details id="e-{esc(e.id)}"><summary>{esc(e.title)}</summary><p>{esc(e.source)} · {esc(e.locator)}</p><blockquote>{esc(e.quote)}</blockquote><p>支持：{esc(e.supports)}</p><p>不能证明：{esc(e.does_not_prove)}</p>'+ (f'<a href="{esc(e.url)}" target="_blank" rel="noopener noreferrer">打开原始来源</a>' if e.url else '')+'</details>' for e in value.evidence_index)
    stages=value.stage_references if value.schema_version=='outcome-evaluation.v3' else [u for u in (value.upgrade_plus_1,value.upgrade_plus_2) if u]
    upgrades=''.join(f'<div><h3>更高阶段参考 · L{u.target_level} · {esc(u.level_name)}</h3><p>作用条件：{esc(u.need)}</p><p>核验依据：{esc("；".join(u.proof_materials))}</p></div>' for u in stages)
    tasks=''
    for filename,t in [('project-material-request',value.next_tasks.project_material),('expert-review-task',value.next_tasks.expert_review),('observation-task',value.next_tasks.observation),('maintenance-task',value.next_tasks.maintenance)]:
        if t:
            (output/f'{filename}.md').write_text(t.body,encoding='utf-8')
            tasks+=f'<details><summary>{esc(t.title)} — {esc(t.summary)}</summary><pre>{esc(t.body)}</pre></details>'
    title=value.outcome_resolution.canonical_name or value.outcome_resolution.user_query
    level=f'L{value.current_level} · {value.level_name}' if value.current_level else '初步 / 待补证'
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>成果影响力报告</title><style>*{box-sizing:border-box}body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f4f7fa;color:#29465d;margin:0;padding:24px;line-height:1.75}main{max-width:1400px;margin:auto;display:grid;grid-template-columns:300px minmax(0,1fr);gap:20px}section,aside{background:white;border:1px solid #dde5ee;border-radius:10px;padding:24px;min-width:0}article{display:grid;gap:20px;min-width:0}h1{font-size:26px}h2{font-size:20px}a{color:#2868a6;margin-right:8px}table{width:100%;border-collapse:collapse}td,th{padding:14px;text-align:left;border-bottom:1px solid #eee;vertical-align:top}details{padding:12px 0;border-bottom:1px solid #eee}summary{cursor:pointer;color:#326ca0}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}p,li,td,th,a{overflow-wrap:anywhere}blockquote{margin:12px 0;padding:12px;border-left:3px solid #91b0cf;background:#f6f9fc}.scroll{overflow:auto}.level{color:#34785f;font-size:28px}.note{color:#a77621}@media(max-width:800px){main{display:block}article{margin-top:20px}table{min-width:600px}}</style><main>'''
    document+=f'<aside><h2>{esc(title)}</h2><p>{esc(value.project_context.project_name)}</p><h3>材料与证据</h3>{evidence_html}</aside><article><section><h2>① 影响力等级判断</h2><p class="note">系统初步判断 · 未记录专家确认</p><h1>{esc(title)}</h1><p>{esc(value.summary)}</p><div class="level">{esc(level)}</div><ul>{reasons}</ul><p>{esc(value.boundary_gap)}</p>{upgrades}</section><section><h2>② 关键判断与证据</h2><div class="scroll"><table><tr><th>关键问题</th><th>项目方材料 / 主张</th><th>评价核验</th></tr>{rows}</table></div></section><section><h2>③ 下一步任务</h2>{tasks or "暂无任务"}</section></article></main></html>'
    (output/'report.html').write_text(document,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('result',type=Path); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); export_artifacts(Assessment.model_validate_json(args.result.read_text(encoding='utf-8')),args.output)
