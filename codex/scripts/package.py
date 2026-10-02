#!/usr/bin/env python3
"""Package the local marketplace, including the pinned upstream editor assets."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
if not (root / 'plugins/drawio/vendor/drawio/webapp/index.html').is_file():
    raise SystemExit('Fetch editor sources first: python3 plugins/drawio/scripts/fetch-source.py')
out = root / 'dist/drawio-codex-0.1.0.zip'
out.parent.mkdir(exist_ok=True)
paths = [root / 'plugins/drawio', root / '.agents', root / 'examples', root / 'README.md', root / 'LICENSE', root / 'scripts', root / 'tests']
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in paths:
        files = path.rglob('*') if path.is_dir() else [path]
        for file in sorted(files):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                archive.write(file, 'drawio-codex/' + str(file.relative_to(root)))
print(f'{out} ({out.stat().st_size / 1024 / 1024:.1f} MiB)')
