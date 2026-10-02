import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/drawio/scripts/drawio.py'
spec = importlib.util.spec_from_file_location('drawio', SCRIPT)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DiagramTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'схема.drawio')

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return d.call('create_diagram', {'path': self.path, 'nodes': [{'id': 'a', 'label': 'A & B'}, {'id': 'b', 'label': 'Сервис'}], 'edges': [{'source': 'a', 'target': 'b'}]})

    def test_roundtrip_and_conflicts(self):
        self.create()
        original = d.call('read_diagram', {'path': self.path})
        self.assertIn('A &amp; B', original['xml'])
        with self.assertRaisesRegex(ValueError, 'File exists'):
            self.create()
        changed = original['xml'].replace('Сервис', 'База')
        d.call('write_diagram', {'path': self.path, 'xml': changed, 'revision': original['revision']})
        with self.assertRaisesRegex(ValueError, 'Conflict'):
            d.call('write_diagram', {'path': self.path, 'xml': original['xml'], 'revision': original['revision']})
        self.assertEqual(d.call('read_diagram', {'path': self.path})['pages'][0]['cells'][3]['value'], 'База')

    def test_compressed_multipage(self):
        graph = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>'
        compressor = zlib.compressobj(wbits=-15)
        encoded = base64.b64encode(compressor.compress(quote(graph, safe='').encode()) + compressor.flush()).decode()
        pages = d.inspect(f'<mxfile><diagram name="A">{encoded}</diagram><diagram name="B">{graph}</diagram></mxfile>')
        self.assertEqual([p['name'] for p in pages], ['A', 'B'])
        self.assertEqual(len(pages[0]['cells']), 2)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            d.checked_path('../bad.drawio')
        with self.assertRaises(ValueError):
            d.model('<!DOCTYPE mxfile><mxfile/>')
        with self.assertRaisesRegex(ValueError, 'unknown node'):
            d.create_xml([{'id': 'a'}], [{'source': 'a', 'target': 'b'}])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            d.create_xml([{'id': 'a'}, {'id': 'a'}], [])

    def test_editor_http_save_auth_and_static_scope(self):
        self.create()
        editor = d.Editor()
        opened = editor.open(Path(self.path))
        try:
            query = '?session=' + opened['session_id']
            headers = {'Authorization': 'Bearer ' + editor.token}
            with self.assertRaises(HTTPError) as error:
                urlopen(editor.base + '/api/document' + query)
            self.assertEqual(error.exception.code, 403)
            data = json.load(urlopen(Request(editor.base + '/api/document' + query, headers=headers)))
            body = json.dumps({'xml': data['xml'].replace('Сервис', 'Новое'), 'revision': data['revision']}).encode()
            result = json.load(urlopen(Request(editor.base + '/api/save' + query, data=body, headers=headers)))
            self.assertNotEqual(result['revision'], data['revision'])
            with self.assertRaises(HTTPError) as conflict:
                urlopen(Request(editor.base + '/api/save' + query, data=body, headers=headers))
            self.assertEqual(conflict.exception.code, 409)
            with self.assertRaises(HTTPError):
                urlopen(editor.base + '/drawio/%2e%2e/%2e%2e/scripts/drawio.py')
            with self.assertRaises(HTTPError):
                urlopen(Request(editor.base + '/api/document' + query, headers=dict(headers, Origin='https://example.com')))
            self.assertIn(b'draw.io', urlopen(editor.base + '/').read())
        finally:
            editor.server.shutdown()
            editor.server.server_close()

    def test_mcp_protocol(self):
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'create_diagram', 'arguments': {'path': self.path, 'nodes': [{'id': 'a', 'label': 'Привет'}]}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'read_diagram', 'arguments': {'path': '/does-not-exist.drawio'}}}
        ]
        result = subprocess.run(['python3', str(SCRIPT), 'mcp'], input='\n'.join(json.dumps(r) for r in requests) + '\n', text=True, capture_output=True, check=True)
        replies = {r['id']: r for r in map(json.loads, result.stdout.splitlines())}
        self.assertEqual(replies[1]['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(len(replies[2]['result']['tools']), 5)
        self.assertFalse(replies[3]['result']['isError'])
        self.assertTrue(replies[4]['result']['isError'])
        self.assertTrue(Path(self.path).exists())


if __name__ == '__main__':
    unittest.main()
