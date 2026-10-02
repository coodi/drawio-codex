"""Manual end-to-end MCP/browser check. Open printed URL, press Enter to export.

Run: python3 tests/browser_smoke.py
Uses the installed plugin when available; the sample lives in this repository.
"""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
installed = Path.home() / '.codex/plugins/cache/drawio-local/drawio/0.1.0/scripts/drawio.py'
script = installed if installed.exists() else root / 'plugins/drawio/scripts/drawio.py'
process = subprocess.Popen([sys.executable, str(script), 'mcp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
ident = 0


def rpc(method, params):
    global ident
    ident += 1
    process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}) + '\n')
    process.stdin.flush()
    response = json.loads(process.stdout.readline())
    assert response['id'] == ident, response
    result = response['result']
    if method == 'tools/call':
        if result.get('isError'):
            raise RuntimeError(result['content'][0]['text'])
        return json.loads(result['content'][0]['text'])
    return result


try:
    rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'browser-smoke', 'version': '1'}})
    path = str(root / 'examples/codex-drawio.drawio')
    opened = rpc('tools/call', {'name': 'open_editor', 'arguments': {'path': path}})
    print(json.dumps(opened), flush=True)
    input('Open URL in Codex, wait for the diagram, then press Enter.\n')
    for fmt in ('svg', 'png'):
        out = root / 'dist' / ('browser-smoke.' + fmt)
        if out.exists():
            raise RuntimeError(f'Remove previous smoke-test output before running: {out}')
        result = rpc('tools/call', {'name': 'export_diagram', 'arguments': {'path': path, 'output': str(out), 'format': fmt}})
        print(json.dumps(result), flush=True)
        data = out.read_bytes()
        assert b'<svg' in data if fmt == 'svg' else data.startswith(b'\x89PNG\r\n\x1a\n')
    print('PASS: installed MCP plugin rendered SVG and PNG via the original draw.io editor.', flush=True)
    input('Press Enter to stop the MCP process.\n')
finally:
    process.terminate()
    process.wait(timeout=5)
