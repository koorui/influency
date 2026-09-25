"""Build a portable skill ZIP excluding caches; installation does not overwrite existing skills."""
import argparse
import os
import shutil
import zipfile
from pathlib import Path

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--install',action='store_true')
    parser.add_argument('--skill',choices=['outcome-impact-evaluation','dual-layer-impact-v19','data-purification-ai-attribution','impact-evaluation-pipeline','project-search-verification'],default='outcome-impact-evaluation')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    skill=root/'skills'/args.skill
    archive=root/'dist'/f'{args.skill}.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(skill.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                z.write(p,Path(skill.name)/p.relative_to(skill))
    print(archive)
    if args.install:
        target=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'/skill.name
        if target.exists():raise SystemExit('Skill already exists; inspect before updating. ZIP still generated.')
        shutil.copytree(skill,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        print('Installed:',target)
