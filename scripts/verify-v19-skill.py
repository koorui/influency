"""Offline acceptance checks. All model responses are simulated; no provider is contacted."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import tempfile

root=Path(__file__).resolve().parents[1]
skill=root/'skills/unified-impact-evaluation'
delivery=root.parent/'9.23/双层影响力工具_v19_交付包_20260923_0735/系统运行版'
spec=importlib.util.spec_from_file_location('v19_wrapper',skill/'scripts/v19.py')
wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
from metric_judgment.indicator_product import IndicatorEvaluationPipeline,build_indicator_product


class OfflineClient:
    available=False
    settings=SimpleNamespace(glm_model='offline-test-only')
    def chat_json(self,system,user,**kwargs):
        payload=json.loads(user)
        if 'dimension' in payload:
            dim=payload['dimension']['question_id']
            data={'status':'待核验','conclusion':'离线协议测试，不构成科研评价。',
                'branch_judgments':[{'branch_id':f'{dim}.{i}','status':'待核验','conclusion':'离线测试','decisive_source_ids':[]} for i in range(1,4)],
                'grade':{'level':'待确认','reason':'离线测试','source_ids':[],'gap_to_next':'真实评价未执行'}}
        elif 'project' in payload:
            data={'overall_judgment':'离线测试，不构成项目结论','scope_impact_level':{'level':'待确认','source_ids':[],'reason':'离线测试'}}
        else:
            data={'overall_conclusion':'离线测试，不构成成果结论','impact_level':{'level':'待确认','source_ids':[],'reason':'离线测试'}}
        return SimpleNamespace(ok=True,data=data,model='offline-test-only',text=json.dumps(data,ensure_ascii=False),raw='',error='',error_type='')


def main():
    manifest=json.loads((skill/'assets/source-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        assert (skill/entry['bundled']).is_file()
    checks={'bundled_source_files':len(manifest['files']),'model_requests':0}
    for pid,ready,count in [('P01',False,0),('P02',True,41),('P06',False,0)]:
        p=delivery/f'backend/workspace_snapshots/{pid}.json'
        result=wrapper.inspect_workspace(p)
        assert result['formal_input_ready']==ready and result['expected_logical_calls']==count
        checks[pid]={'input_ready':ready,'logical_calls':count,'missing_local_sources':result['unavailable_source_count']}
        if not ready:
            try:IndicatorEvaluationPipeline(OfflineClient.settings,OfflineClient()).run(wrapper.read(p))
            except ValueError:pass
            else:raise AssertionError('Frozen outcome gate was bypassed')
    workspace=wrapper.read(delivery/'backend/workspace_snapshots/P02.json')
    with contextlib.redirect_stdout(io.StringIO()):
        result=IndicatorEvaluationPipeline(OfflineClient.settings,OfflineClient()).run(workspace,model='offline-test-only',parallelism=2)
    checked=wrapper.validate_result(result)
    assert not checked['valid'], 'Pending offline grades must not pass the completed-report contract'
    assert result['llm_trace']['summary']['provider_request_count']==0
    assert result['run']['completed_call_count']==41
    for field in ['specific_layer','global_layer','system_collaboration']:
        assert field in result['project_synthesis']
    product=build_indicator_product(workspace,result)
    assert isinstance(product,dict) and product
    checks['offline_pipeline']='35 dimensions + 5 outcome syntheses + 1 project synthesis; pending grades only'
    historical=next((delivery/'backend/results').rglob('*.json'))
    old=wrapper.validate_result(wrapper.read(historical))
    assert not old['valid'] and any('impact_level' in e for e in old['errors'])
    checks['historical_missing_grades_rejected']=True
    # The offline command must work even without site-packages / model SDK.
    command=[sys.executable,'-S',str(skill/'scripts/v19.py'),'inspect','--workspace',str(delivery/'backend/workspace_snapshots/P02.json')]
    proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env={**__import__('os').environ,'PYTHONIOENCODING':'utf-8'})
    assert proc.returncode==0,proc.stderr
    checks['stdlib_only_inspection']=True
    with tempfile.TemporaryDirectory(prefix='v19-check-') as temp:
        p=Path(temp)/'check.json'
        wrapper.write_check(p,{'check':True})
        try:wrapper.write_check(p,{'check':False})
        except FileExistsError:pass
        else:raise AssertionError('Existing check report overwritten')
    checks['report_overwrite_protected']=True
    out=root/'docs/v19-skill-verification.json'
    out.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
