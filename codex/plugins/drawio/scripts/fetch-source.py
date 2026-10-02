#!/usr/bin/env python3
"""Fetch the exact upstream web editor revision; no build toolchain required."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
metadata = json.loads((root / 'vendor/drawio/source.json').read_text())
destination = root / 'vendor/drawio/webapp'
if destination.exists():
    raise SystemExit('Editor already present. Remove vendor/drawio/webapp explicitly to fetch again.')
with tempfile.TemporaryDirectory(prefix='drawio-source-') as directory:
    source = Path(directory) / 'drawio'
    def git(*args):
        subprocess.run(['git', '-C', str(source), *args], check=True)
    source.mkdir()
    git('init', '--quiet')
    git('remote', 'add', 'origin', metadata['repository'])
    git('config', 'core.sparseCheckout', 'true')
    (source / '.git/info/sparse-checkout').write_text('/src/main/webapp/\n/LICENSE\n/VERSION\n')
    git('fetch', '--depth=1', '--filter=blob:none', 'origin', metadata['commit'])
    git('checkout', '--detach', 'FETCH_HEAD')
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != metadata['commit']:
        raise SystemExit('Unexpected source revision')
    shutil.copytree(source / metadata['path'], destination)
    for name in ('LICENSE', 'VERSION'):
        shutil.copy2(source / name, destination.parent / name)
print(destination)
