"""Load the version-controlled, self-contained skill contract without importing providers."""
import importlib.util
import sys
from pathlib import Path

SKILL_ROOT=Path(__file__).resolve().parents[2]/'skills'/'outcome-impact-evaluation'


def load_module(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,SKILL_ROOT/'scripts'/filename)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


contract=load_module('assessment_contract','assessment_contract.py')
exporter=load_module('assessment_export','export_artifacts.py')
