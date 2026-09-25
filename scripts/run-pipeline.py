"""Local operator entrypoint. Does not expose arbitrary executable paths."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.pipeline_store import PipelineStore,STAGES
from app.pipeline_service import run_pipeline

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['create','run','status','amend'])
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--restart-stage',choices=STAGES)
    args=parser.parse_args()
    store=PipelineStore(args.directory)
    if args.command in ('create','amend') and not args.input:parser.error('--input is required')
    if args.command=='create':result=store.create(json.loads(args.input.read_text(encoding='utf-8')))
    elif args.command=='amend':
        if not args.restart_stage:parser.error('--restart-stage is required')
        result=store.amend(json.loads(args.input.read_text(encoding='utf-8')),args.restart_stage)
    elif args.command=='run':result=run_pipeline(args.directory)
    else:result=store.read()
    print(json.dumps({'status':result['status'],'stages':result['stages']},ensure_ascii=False,indent=2))
