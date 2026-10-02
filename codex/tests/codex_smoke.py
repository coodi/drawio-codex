"""Check the installed plugin through Codex app-server, without calling a model."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

binary = os.environ.get('DRAWIO_CODEX_BIN') or shutil.which('codex')
if not binary:
    bundled = Path('/usr/lib/chatgpt/resources/codex')
    binary = str(bundled) if bundled.exists() else None
if not binary:
    raise SystemExit('Set DRAWIO_CODEX_BIN to the Codex executable')
process = subprocess.Popen([binary, 'app-server', '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
selector = selectors.DefaultSelector()
selector.register(process.stdout, selectors.EVENT_READ)


def rpc(ident, method, params):
    process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}) + '\n')
    process.stdin.flush()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if not selector.select(1):
            continue
        line = process.stdout.readline()
        if not line:
            raise RuntimeError('Codex app-server exited')
        response = json.loads(line)
        if response.get('id') == ident:
            if 'error' in response:
                raise RuntimeError(response['error'])
            return response['result']
    raise TimeoutError(method)


try:
    rpc(1, 'initialize', {'clientInfo': {'name': 'drawio-verification', 'version': '1.0'}})
    result = rpc(2, 'mcpServerStatus/list', {'detail': 'toolsAndAuthOnly', 'limit': 100})
    servers = [s for s in result['data'] if s.get('pluginId') == 'drawio@drawio-local']
    assert len(servers) == 1, 'Install drawio@drawio-local first'
    server = servers[0]
    assert server.get('toolsError') is None, server.get('toolsError')
    expected = {'create_diagram', 'read_diagram', 'write_diagram', 'open_editor', 'export_diagram'}
    assert set(server['tools']) == expected, server['tools']
    print('PASS: Codex discovered all five tools of drawio@drawio-local.')
finally:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    selector.close()
