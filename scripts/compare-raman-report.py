"""Post-evaluation comparison; reference answers are never used as model inputs."""
import argparse
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--result',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    actual=json.loads(a.result.read_text(encoding='utf-8'))
    source=(ROOT.parent/'9.23/成果影响力评价系统_9232000.html').read_text(encoding='utf-8')
    match=re.search(r'const DB\s*=\s*',source)
    if not match:raise ValueError('Reference HTML has no readable data object')
    reference,_=json.JSONDecoder().raw_decode(source[match.end():])
    r=reference['raman']
    report={'comparison_only':True,'model_input_includes_reference':False,
        'reference':{'title':r['name'],'level':r['grade'],'level_name':r['gradeName'],'summary':r['achievement']},
        'actual':{k:actual.get(k) for k in ['evaluation_status','current_level','level_name','summary','boundary_gap']},
        'same_level':actual['current_level']==r['grade'],
        'evidence_records':len(actual['evidence_index']),
        'project_evidence_records':sum(e['kind']=='project' for e in actual['evidence_index']),
        'external_evidence_records':sum(e['kind']=='external' for e in actual['evidence_index']),
        'manual_review_required':True,
        'review_focus':'核对L2是否包括成果对项目内部研发真实任务的可核验作用；不得把尚无生物成像或外部应用自动等同于内部任务也没有作用。不得为了匹配参考答案直接修改模型等级。'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'same_level':report['same_level'],'actual':actual['current_level'],'reference':r['grade'],'evidence_records':report['evidence_records']},ensure_ascii=False))
