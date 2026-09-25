"""Run the unchanged delivered DCA library in a fresh output directory."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from dca_integration.cli import build_parser,main

if __name__=='__main__':
    args=build_parser().parse_args()
    output=Path(args.output).resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise SystemExit('Choose a new output directory outside the skill; existing outputs are not overwritten.')
    sys.exit(main())
