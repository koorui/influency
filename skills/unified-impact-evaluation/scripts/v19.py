"""Portable wrapper around the unchanged delivered v19 engine."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
STANDARD='outcome-d1-d7-evaluation.v19'


def read(path):
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('Expected a JSON object')
    return value


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def write_check(path,value):
    if path.resolve().is_relative_to(ROOT):raise ValueError('Check output must be outside the skill')
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def inspect_workspace(path):
    from metric_judgment.indicator_product import build_indicator_input_contract
    workspace=read(path)
    if workspace.get('schema_version')!='indicator-workspace.v6':
        raise ValueError('Expected indicator-workspace.v6; raw documents are not pipeline inputs')
    contract=build_indicator_input_contract(workspace)
    refs=set()
    def scan(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in ('source_file','source_path','file_path','archive_file') and isinstance(v,str) and v and not v.startswith(('http://','https://')):
                    refs.add(v)
                scan(v)
        elif isinstance(value,list):
            for v in value:scan(v)
    scan(workspace)
    missing=[]
    for value in sorted(refs):
        p=Path(value)
        if not p.is_absolute():p=Path(path).resolve().parent/p
        if not p.exists():missing.append(value)
    n=len(contract['outcome_cards'])
    ready=bool(n and contract['formal_evaluation_ready'])
    return {'standard_version':STANDARD,'project_id':workspace.get('project_profile',{}).get('project_id'),
        'formal_input_ready':ready,'outcome_count':n,'expected_logical_calls':8*n+1 if ready else 0,
        'receipts':contract['receipts'],'missing_required':[r['name'] for r in contract['receipts'] if r['required'] and r['state']!='已接收'],
        'unavailable_source_count':len(missing),'unavailable_source_examples':missing[:12],
        'note':'Input readiness is not fact verification. Original file paths may require remapping.'}


def validate_result(result):
    errors=[]
    run=result.get('run') or {}
    modern=run.get('output_contract_version')=='structured-dimension-facts-with-grades.v4'
    if result.get('schema_version')!='indicator-evaluation.run.v5':errors.append('Unexpected run schema')
    if run.get('standard_version')!=STANDARD:errors.append('Not the current v19 standard')
    outcomes=result.get('outcomes') or []
    expected=8*len(outcomes)+1
    if not outcomes:errors.append('No evaluated outcomes')
    if not result.get('formal'):errors.append('Engine did not mark this run formal')
    if run.get('expected_call_count')!=expected or run.get('completed_call_count')!=expected:errors.append('Logical calls incomplete or inconsistent')
    def level(obj,key,prefix,max_level,label):
        record=obj.get(key) or {}
        val=record.get('level')
        if modern:
            state=record.get('assessment_state')
            if prefix=='G' and state in ('insufficient_evidence','not_applicable','conflict') and val is None and record.get('reason'):return
            if prefix=='L' and val is None and record.get('reason'):return
            if prefix=='G' and state!='assessed':errors.append(f'{label}: invalid assessment state')
            if val is not None and not record.get('source_ids'):errors.append(f'{label}: no grade evidence')
        if val not in [f'{prefix}{i}' for i in range(1,max_level+1)]:errors.append(f'{label}: missing/invalid {key}.level')
    def pending_verdicts(node):
        if isinstance(node,dict):
            for key,value in node.items():
                if key in ('status','level') and isinstance(value,str) and value in ('待核验','待确认','初步评价'):
                    errors.append('Completed report contains a pending verdict')
                pending_verdicts(value)
        elif isinstance(node,list):
            for value in node:pending_verdicts(value)
    for outcome in outcomes:
        label=outcome.get('outcome_id','unknown')
        dims=outcome.get('dimensions') or []
        if len(dims)!=7 or {d.get('dimension_id') for d in dims}!={f'D{i}' for i in range(1,8)}:errors.append(f'{label}: D1-D7 incomplete')
        for d in dims:level(d,'grade','G',5,f'{label}/{d.get("dimension_id")}')
        level(outcome.get('synthesis') or {},'impact_level','L',6,label)
    level(result.get('project_synthesis') or {},'scope_impact_level','L',6,'project scope')
    if not modern:
        for outcome in outcomes:pending_verdicts(outcome)
        pending_verdicts(result.get('project_synthesis') or {})
    return {'valid':not errors,'errors':errors,'standard_version':STANDARD,'note':'Structure only; scientific conclusions still require review.'}


def engine_run(args):
    # Load only explicitly provided service settings; the vendored config has legacy defaults.
    os.environ['PYTHON_DOTENV_DISABLED']='1'
    import dotenv
    dotenv.load_dotenv=lambda *a,**k:False
    from impact_eval.config import Settings
    from metric_judgment.llm import LLMClient
    from metric_judgment.indicator_product import IndicatorEvaluationPipeline,build_indicator_product
    workspace=read(args.workspace)
    config=Settings(glm_api_key=os.environ['V19_API_KEY'],glm_base_url=os.environ['V19_BASE_URL'],glm_model=os.environ['V19_MODEL'],use_llm=True,llm_timeout=args.request_timeout,output_dir=args.output_dir)
    result=IndicatorEvaluationPipeline(config,LLMClient(config)).run(workspace,model=config.glm_model,timeout=args.request_timeout,parallelism=args.parallelism)
    write(args.output_dir/'evaluation-run.json',result)
    write(args.output_dir/'product.json',build_indicator_product(workspace,result))
    checked=validate_result(result);write(args.output_dir/'validation.json',checked)
    return 0 if checked['valid'] else 3


def run(args):
    report=inspect_workspace(args.workspace)
    if not report['formal_input_ready']:raise ValueError('Required input missing: '+', '.join(report['missing_required']))
    provider_environment=getattr(args,'provider_environment',os.environ)
    for key in ['V19_API_KEY','V19_BASE_URL','V19_MODEL']:
        if not provider_environment.get(key):raise ValueError('Explicit configuration required: '+key)
    endpoint=urlsplit(provider_environment['V19_BASE_URL'])
    if endpoint.scheme not in ('https','http') or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError('V19_BASE_URL must be an HTTP(S) service URL without credentials, query or fragment')
    output=args.output_dir.resolve()
    if output.is_relative_to(ROOT) or output==args.workspace.resolve().parent:
        raise ValueError('Choose a new output directory outside the skill and input directory')
    output.mkdir(parents=True,exist_ok=False)
    args.output_dir=output
    write(output/'preflight.json',report)
    manifest={'standard_version':STANDARD,'model':provider_environment['V19_MODEL'],'base_url':provider_environment['V19_BASE_URL'],
        'expected_logical_calls':report['expected_logical_calls'],'status':'running'}
    write(output/'run-manifest.json',manifest)
    command=[sys.executable,str(Path(__file__).resolve()),'_engine','--workspace',str(args.workspace.resolve()),'--output-dir',str(output),'--request-timeout',str(args.request_timeout),'--parallelism',str(args.parallelism)]
    kw={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    with (output/'stdout.log').open('wb') as out,(output/'stderr.log').open('wb') as err:
        proc=subprocess.Popen(command,stdout=out,stderr=err,cwd=output,env=dict(provider_environment),**kw)
        try: code=proc.wait(timeout=args.total_timeout)
        except subprocess.TimeoutExpired:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            else:os.killpg(proc.pid,signal.SIGKILL)
            proc.wait(timeout=15);code=124
    manifest['status']='completed' if code==0 else 'timed_out' if code==124 else 'failed'
    manifest['exit_code']=code;write(output/'run-manifest.json',manifest)
    print(json.dumps({'status':manifest['status'],'output_dir':str(output)},ensure_ascii=False))
    return code


def main():
    parser=argparse.ArgumentParser(description='Original v19 double-layer evaluation engine')
    sub=parser.add_subparsers(dest='command',required=True)
    check=sub.add_parser('inspect');check.add_argument('--workspace',required=True,type=Path);check.add_argument('--output',type=Path)
    valid=sub.add_parser('validate');valid.add_argument('--result',required=True,type=Path);valid.add_argument('--output',type=Path)
    for name in ('run','_engine'):
        p=sub.add_parser(name);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
        p.add_argument('--request-timeout',type=int,default=240);p.add_argument('--parallelism',type=int,choices=range(1,9),default=2);p.add_argument('--total-timeout',type=int,default=1800)
    args=parser.parse_args()
    if args.command in ('run','_engine') and (not 10<=args.request_timeout<=900 or not 1<=args.total_timeout<=14400):raise ValueError('Invalid timeout bounds')
    if args.command=='inspect':
        report=inspect_workspace(args.workspace)
        if args.output:write_check(args.output,report)
        print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['formal_input_ready'] else 2
    if args.command=='validate':
        report=validate_result(read(args.result))
        if args.output:write_check(args.output,report)
        print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['valid'] else 3
    return engine_run(args) if args.command=='_engine' else run(args)


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,FileExistsError,KeyError) as exc:
        print(f'Cannot proceed: {exc}',file=sys.stderr);sys.exit(2)
