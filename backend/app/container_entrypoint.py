"""Copy explicitly mounted CLI credentials into this container's writable home."""
import os
from pathlib import Path
import shutil
import sys


def main():
    home = Path(os.environ.get('CODEX_HOME', '/home/app/.codex'))
    for name, source in [('config.toml', '/run/secrets/relay_config'), ('auth.json', '/run/secrets/relay_auth')]:
        if Path(source).is_file():
            home.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination = home / name
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
    if len(sys.argv) < 2:
        raise SystemExit('Container command is required')
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
