"""Check deployed data, CLI files and skill imports without sending a model request."""
import json
import os
from pathlib import Path
import subprocess
from sqlalchemy import select, func
from .config import settings
from .db import Session
from .models import User, Material
from .skill_loader import SKILL_ROOT
from .pipeline_stages import SKILLS


def main():
    home = Path(os.environ['CODEX_HOME'])
    assert (home / 'config.toml').is_file(), 'Relay config missing'
    assert json.loads((home / 'auth.json').read_text()).get('OPENAI_API_KEY'), 'Relay authentication missing'
    assert (SKILL_ROOT / 'SKILL.md').is_file(), 'Evaluation skill missing'
    assert (SKILLS / 'unified-impact-evaluation/scripts/v19.py').is_file(), 'v19 runtime missing'
    subprocess.run([settings().codex_binary, '--version'], check=True)
    with Session() as db:
        count = db.scalar(select(func.count()).select_from(User))
        materials = list(db.scalars(select(Material)))
        for material in materials:
            original = Path(settings().storage_dir) / material.storage_key
            assert original.is_file() and original.stat().st_size == material.size, 'Original material missing'
            assert material.text.strip(), 'Extracted text missing'
    print(json.dumps({'accounts': count, 'materials': len(materials), 'relay_auth_configured': True,
                      'adapter': settings().evaluation_adapter, 'v19_transport': settings().v19_transport,
                      'cli_sandbox_mode': settings().codex_sandbox_mode,
                      'model_request_sent': False}))


if __name__ == '__main__':
    main()
