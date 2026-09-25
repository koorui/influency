import importlib.util
import sys
from pathlib import Path

SEARCH_SKILL_ROOT=Path(__file__).resolve().parents[2]/'skills/project-search-verification'
spec=importlib.util.spec_from_file_location('project_search_contract',SEARCH_SKILL_ROOT/'scripts/search_contract.py')
contract=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=contract
spec.loader.exec_module(contract)
