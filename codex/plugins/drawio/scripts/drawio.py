#!/usr/bin/env python3
"""Local draw.io file tools, editor bridge and newline-delimited MCP stdio server."""
from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, quote, unquote, urlsplit
import uuid
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 16 * 1024 * 1024
LOCK = threading.RLock()


def digest(xml):
    return hashlib.sha256(xml.encode('utf-8')).hexdigest()


def model(xml):
    if not isinstance(xml, str) or len(xml.encode('utf-8')) > MAX_BYTES:
        raise ValueError('XML must be a string smaller than 16 MiB')
    if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('DTD and XML entities are unsupported')
    tree = ET.fromstring(xml)
    if tree.tag == 'mxGraphModel':
        return tree
    if tree.tag != 'mxfile' or not tree.findall('diagram'):
        raise ValueError('Expected mxfile with diagram pages or mxGraphModel')
    for page in tree.findall('diagram'):
        if page.find('mxGraphModel') is None:
            data = base64.b64decode((page.text or '').strip(), validate=True)
            inflater = zlib.decompressobj(-15)
            raw = inflater.decompress(data, MAX_BYTES + 1)
            if len(raw) > MAX_BYTES or not inflater.eof:
                raise ValueError('Compressed page too large or incomplete')
            decoded = unquote(raw.decode('utf-8'))
            page.text = None
            page.append(model(decoded))
    return tree


def serialize(tree):
    return ET.tostring(tree, encoding='unicode')


def checked_path(path):
    if not isinstance(path, str) or not path:
        raise ValueError('Provide an absolute .drawio path')
    result = Path(path).expanduser()
    if not result.is_absolute():
        raise ValueError('Paths must be absolute')
    result = result.resolve()
    if result.suffix.lower() != '.drawio':
        raise ValueError('Only .drawio files are supported')
    return result


def read_xml(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Diagram larger than 16 MiB')
    xml = path.read_text(encoding='utf-8')
    model(xml)
    return xml


def atomic_write(path, xml, expected=None, overwrite=True):
    model(xml)
    with LOCK:
        if path.exists():
            if not overwrite:
                raise ValueError('File exists; use overwrite=true explicitly')
            current = read_xml(path)
            if expected is not None and digest(current) != expected:
                raise ValueError('Conflict: file changed. Read again before applying edits.')
        elif expected is not None:
            raise ValueError('Conflict: file was removed')
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(xml)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return {'path': str(path), 'revision': digest(xml)}


def create_xml(nodes, edges, title='Page-1'):
    tree = ET.Element('mxfile', host='drawio-codex', compressed='false')
    page = ET.SubElement(tree, 'diagram', id='page-1', name=title)
    graph = ET.SubElement(page, 'mxGraphModel', grid='1', gridSize='10', page='1', pageWidth='1169', pageHeight='827')
    root = ET.SubElement(graph, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    ids = {'0', '1'}
    for index, node in enumerate(nodes):
        ident = str(node.get('id', f'n{index+1}'))
        if ident in ids:
            raise ValueError('Duplicate cell id: ' + ident)
        ids.add(ident)
        cell = ET.SubElement(root, 'mxCell', id=ident, value=str(node.get('label', ident)), vertex='1', parent='1', style=node.get('style', 'rounded=1;whiteSpace=wrap;html=0;fillColor=#dae8fc;strokeColor=#6c8ebf;'))
        geometry = {'x': node.get('x', 80 + (index % 4) * 220), 'y': node.get('y', 80 + (index // 4) * 140), 'width': node.get('width', 160), 'height': node.get('height', 70)}
        if not all(isinstance(v, (int, float)) and abs(v) < 100000 for v in geometry.values()):
            raise ValueError('Invalid node geometry')
        if geometry['width'] <= 0 or geometry['height'] <= 0:
            raise ValueError('Node dimensions must be positive')
        ET.SubElement(cell, 'mxGeometry', **{k: str(v) for k, v in geometry.items()}, **{'as': 'geometry'})
    node_ids = ids - {'0', '1'}
    for index, edge in enumerate(edges):
        ident = str(edge.get('id', f'e{index+1}'))
        if ident in ids:
            raise ValueError('Duplicate cell id: ' + ident)
        ids.add(ident)
        source, target = str(edge['source']), str(edge['target'])
        if source not in node_ids or target not in node_ids:
            raise ValueError('Edge refers to an unknown node')
        cell = ET.SubElement(root, 'mxCell', id=ident, value=str(edge.get('label', '')), edge='1', parent='1', source=source, target=target, style=edge.get('style', 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;'))
        ET.SubElement(cell, 'mxGeometry', relative='1', **{'as': 'geometry'})
    return serialize(tree)


def inspect(xml):
    tree = model(xml)
    graphs = [('Page-1', tree)] if tree.tag == 'mxGraphModel' else [(p.get('name', ''), p.find('mxGraphModel')) for p in tree.findall('diagram')]
    return [{'name': name, 'cells': [dict(c.attrib, geometry=dict(c.find('mxGeometry').attrib) if c.find('mxGeometry') is not None else {}) for c in graph.iter('mxCell')]} for name, graph in graphs]


class Editor:
    def __init__(self):
        self.sessions = {}
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.base = None

    def start(self):
        with LOCK:
            if self.server:
                return
            if not (ROOT / 'vendor/drawio/webapp/index.html').exists():
                raise ValueError('Editor sources missing. Run scripts/fetch-source.py first.')
            self.server = ThreadingHTTPServer(('127.0.0.1', 0), self.handler())
            self.base = f'http://127.0.0.1:{self.server.server_port}'
            threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def open(self, path):
        self.start()
        with LOCK:
            sid = next((sid for sid, session in self.sessions.items() if session['path'] == path), None)
            if sid is None:
                sid = uuid.uuid4().hex
                self.sessions[sid] = {'path': path, 'commands': [], 'exports': {}, 'active': 0}
        return {'path': str(path), 'session_id': sid, 'url': f'{self.base}/?session={sid}#token={self.token}'}

    def handler(self):
        editor = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, value, mime='application/json'):
                data = json.dumps(value, ensure_ascii=False).encode() if mime == 'application/json' else value
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(data)

            def valid_host(self):
                if self.headers.get('Host') != urlsplit(editor.base).netloc:
                    self.reply(403, {'error': 'Invalid Host'})
                    return False
                return True

            def session(self):
                if self.headers.get('Authorization') != 'Bearer ' + editor.token:
                    raise PermissionError('Missing session token')
                origin = self.headers.get('Origin')
                if origin and origin != editor.base:
                    raise PermissionError('Invalid Origin')
                sid = parse_qs(urlsplit(self.path).query).get('session', [''])[0]
                if sid not in editor.sessions:
                    raise ValueError('Unknown editor session')
                return editor.sessions[sid]

            def do_GET(self):
                if not self.valid_host():
                    return
                try:
                    route = unquote(urlsplit(self.path).path)
                    if route == '/api/document':
                        session = self.session()
                        with LOCK:
                            xml = read_xml(session['path'])
                            commands = session['commands'][:]
                            session['commands'].clear()
                            session['active'] = time.monotonic()
                        self.reply(200, {'xml': xml, 'revision': digest(xml), 'name': session['path'].name, 'commands': commands})
                        return
                    if route.startswith('/drawio/'):
                        directory = (ROOT / 'vendor/drawio/webapp').resolve()
                        file = (directory / route[len('/drawio/'):]).resolve()
                        if not file.is_relative_to(directory) or any(part in ('WEB-INF', 'META-INF') for part in file.relative_to(directory).parts):
                            raise PermissionError('Invalid static path')
                    elif route in ('/', '/bridge.js'):
                        file = ROOT / 'web' / ('index.html' if route == '/' else 'bridge.js')
                    else:
                        self.reply(404, {'error': 'Not found'})
                        return
                    if not file.is_file():
                        self.reply(404, {'error': 'Not found'})
                        return
                    self.reply(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                except PermissionError as error:
                    self.reply(403, {'error': str(error)})
                except (ValueError, OSError, ET.ParseError) as error:
                    self.reply(400, {'error': str(error)})

            def do_POST(self):
                if not self.valid_host():
                    return
                try:
                    session = self.session()
                    length = int(self.headers.get('Content-Length', '0'))
                    if length <= 0 or length > MAX_BYTES:
                        raise ValueError('Invalid request size')
                    body = json.loads(self.rfile.read(length))
                    route = urlsplit(self.path).path
                    if route == '/api/save':
                        if not isinstance(body.get('revision'), str):
                            raise ValueError('Revision required')
                        result = atomic_write(session['path'], body['xml'], expected=body['revision'])
                        self.reply(200, result)
                    elif route == '/api/export':
                        with LOCK:
                            entry = session['exports'].get(body.get('id'))
                            if entry is None:
                                raise ValueError('Unknown export request')
                            entry['result'] = body
                            entry['event'].set()
                        self.reply(200, {'ok': True})
                    else:
                        self.reply(404, {'error': 'Not found'})
                except PermissionError as error:
                    self.reply(403, {'error': str(error)})
                except (ValueError, KeyError, OSError, ET.ParseError) as error:
                    self.reply(409 if str(error).startswith('Conflict:') else 400, {'error': str(error)})
        return Handler

    def export(self, path, output, fmt):
        opened = self.open(path)
        session = self.sessions[opened['session_id']]
        output = Path(output).expanduser()
        if not output.is_absolute() or output.suffix.lower() != '.' + fmt:
            raise ValueError('Provide an absolute output path matching the export format')
        if output.exists():
            raise ValueError('Export output exists. Choose a new output path.')
        if time.monotonic() - session['active'] > 10:
            raise ValueError('Open the editor URL in Codex first: ' + opened['url'])
        ident = uuid.uuid4().hex
        entry = {'event': threading.Event()}
        with LOCK:
            session['exports'][ident] = entry
            session['commands'].append({'id': ident, 'action': 'export', 'format': fmt, 'xml': read_xml(path)})
        try:
            if not entry['event'].wait(30):
                raise ValueError('Export timed out. Keep the editor tab open and retry.')
            result = entry['result']
            if result.get('error'):
                raise ValueError(result['error'])
            data = result['data']
            prefix, separator, payload = data.partition(',')
            expected_mime = 'image/svg+xml' if fmt == 'svg' else 'image/png'
            if not separator or not prefix.startswith('data:' + expected_mime):
                raise ValueError('Unexpected export data')
            blob = base64.b64decode(payload, validate=True) if ';base64' in prefix else unquote(payload).encode()
            if len(blob) > MAX_BYTES:
                raise ValueError('Export too large')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as stream:
                stream.write(blob)
            return {'path': str(output), 'format': fmt, 'bytes': len(blob)}
        finally:
            with LOCK:
                session['exports'].pop(ident, None)
                session['commands'][:] = [c for c in session['commands'] if c['id'] != ident]


EDITOR = Editor()


def call(name, args):
    path = checked_path(args.get('path'))
    if name == 'create_diagram':
        xml = args.get('xml') or create_xml(args.get('nodes', []), args.get('edges', []), args.get('title', 'Page-1'))
        return atomic_write(path, xml, overwrite=args.get('overwrite', False))
    if name == 'read_diagram':
        xml = read_xml(path)
        return {'path': str(path), 'xml': xml, 'revision': digest(xml), 'pages': inspect(xml)}
    if name == 'write_diagram':
        return atomic_write(path, args['xml'], expected=args['revision'])
    if name == 'open_editor':
        read_xml(path)
        return EDITOR.open(path)
    if name == 'export_diagram':
        fmt = args.get('format', 'svg')
        if fmt not in ('svg', 'png'):
            raise ValueError('Supported formats: svg, png')
        return EDITOR.export(path, args['output'], fmt)
    raise ValueError('Unknown tool: ' + name)


def schema(properties, required):
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


PATH = {'type': 'string', 'description': 'Absolute path to a .drawio file on this computer.'}
TEXT = {'type': 'string'}
NODE = schema({'id': TEXT, 'label': TEXT, 'x': {'type': 'number'}, 'y': {'type': 'number'}, 'width': {'type': 'number'}, 'height': {'type': 'number'}, 'style': TEXT}, ['id', 'label'])
EDGE = schema({'id': TEXT, 'source': TEXT, 'target': TEXT, 'label': TEXT, 'style': TEXT}, ['source', 'target'])
TOOLS = [
    {'name': 'create_diagram', 'description': 'Create a draw.io document from nodes and edges, or full XML. Existing files are protected by default.', 'inputSchema': schema({'path': PATH, 'nodes': {'type': 'array', 'items': NODE}, 'edges': {'type': 'array', 'items': EDGE}, 'title': TEXT, 'xml': TEXT, 'overwrite': {'type': 'boolean'}}, ['path'])},
    {'name': 'read_diagram', 'description': 'Read XML, revision and cells of all pages, including compressed draw.io pages.', 'inputSchema': schema({'path': PATH}, ['path'])},
    {'name': 'write_diagram', 'description': 'Replace diagram XML using the revision returned by read_diagram. Rejects conflicting edits.', 'inputSchema': schema({'path': PATH, 'xml': TEXT, 'revision': TEXT}, ['path', 'xml', 'revision'])},
    {'name': 'open_editor', 'description': 'Start the original local draw.io editor and return its URL. Open URL with open_in_codex browser target. Server stays alive with this MCP process.', 'inputSchema': schema({'path': PATH}, ['path'])},
    {'name': 'export_diagram', 'description': 'Export SVG or PNG using an already open local editor tab. Keep the tab active; render timeout is 30 seconds. Output must be a new file.', 'inputSchema': schema({'path': PATH, 'output': TEXT, 'format': {'type': 'string', 'enum': ['svg', 'png']}}, ['path', 'output', 'format'])},
]
for tool in TOOLS:
    tool['annotations'] = {'readOnlyHint': tool['name'] == 'read_diagram', 'destructiveHint': tool['name'] in ('create_diagram', 'write_diagram'), 'idempotentHint': tool['name'] in ('read_diagram', 'open_editor'), 'openWorldHint': False}


def mcp():
    output_lock = threading.Lock()

    def send(response):
        with output_lock:
            print(json.dumps(response, ensure_ascii=False), flush=True)

    def handle(request):
        ident = request.get('id')
        if ident is None:
            return
        response = {'jsonrpc': '2.0', 'id': ident}
        try:
            method, params = request.get('method'), request.get('params', {})
            if method == 'initialize':
                response['result'] = {'protocolVersion': params.get('protocolVersion', '2024-11-05'), 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'drawio-codex', 'version': '0.1.0'}}
            elif method == 'ping':
                response['result'] = {}
            elif method == 'tools/list':
                response['result'] = {'tools': TOOLS}
            elif method == 'tools/call':
                try:
                    value = call(params['name'], params.get('arguments', {}))
                    response['result'] = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}], 'isError': False}
                except Exception as error:
                    response['result'] = {'content': [{'type': 'text', 'text': str(error)}], 'isError': True}
            else:
                response['error'] = {'code': -32601, 'message': 'Method not found'}
        except Exception as error:
            response['error'] = {'code': -32602, 'message': str(error)}
        send(response)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Expected JSON-RPC object')
                pool.submit(handle, request)
            except ValueError:
                send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON'}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('mcp')
    cli = commands.add_parser('call')
    cli.add_argument('tool', choices=[t['name'] for t in TOOLS])
    cli.add_argument('arguments', help='JSON arguments')
    serve = commands.add_parser('serve')
    serve.add_argument('path', help='Absolute path to .drawio document')
    options = parser.parse_args()
    if options.command == 'mcp':
        mcp()
    elif options.command == 'call':
        if options.tool in ('open_editor', 'export_diagram'):
            parser.error('Use serve for a persistent editor; exports require the persistent MCP server')
        print(json.dumps(call(options.tool, json.loads(options.arguments)), ensure_ascii=False))
    else:
        path = checked_path(options.path)
        read_xml(path)
        print(json.dumps(EDITOR.open(path)), flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            EDITOR.server.shutdown()


if __name__ == '__main__':
    main()
