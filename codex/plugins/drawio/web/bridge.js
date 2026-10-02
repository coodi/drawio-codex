'use strict';
const frame = document.getElementById('editor');
const status = document.getElementById('status');
const recovery = document.getElementById('recovery');
const session = new URLSearchParams(location.search).get('session');
const token = new URLSearchParams(location.hash.slice(1)).get('token');
let revision, name, loaded = false, busy = false, pending = null, unsaved = null, conflict = false;
let exportId = null, exportTimer = null;
function message(text, error = false) { status.textContent = text; status.classList.toggle('error', error); }
async function api(route, body) {
  const response = await fetch(`/api/${route}?session=${encodeURIComponent(session)}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, ...(body ? {'Content-Type': 'application/json'} : {}) },
    ...(body ? {body: JSON.stringify(body)} : {})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}
function send(data) { frame.contentWindow.postMessage(JSON.stringify(data), location.origin); }
function load(data) {
  revision = data.revision; name = data.name;
  send({action: 'load', xml: data.xml, title: name, autosave: 1, saveAndExit: 0});
  send({action: 'status', message: 'Сохранено локально', modified: false});
  loaded = true;
  message(`${name} · локальный файл`);
}
async function save(xml) {
  unsaved = xml; pending = xml;
  if (busy || conflict) return;
  busy = true;
  try {
    while (pending !== null) {
      const value = pending; pending = null;
      message(`${name} · сохранение…`);
      const result = await api('save', {xml: value, revision});
      revision = result.revision;
    }
    unsaved = null;
    recovery.classList.remove('visible');
    send({action: 'status', message: 'Сохранено локально', modified: false});
    message(`${name} · сохранено`);
  } catch (error) {
    conflict = true;
    recovery.classList.add('visible');
    message(`Сохранение остановлено: ${error.message}. Скачайте правки перед перезагрузкой.`, true);
  } finally { busy = false; }
}
window.addEventListener('message', async event => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow || typeof event.data !== 'string') return;
  let data;
  try { data = JSON.parse(event.data); } catch { return; }
  try {
    if (data.event === 'init') load(await api('document'));
    else if (data.event === 'load') send({action: 'fit', border: 24, maxScale: 1});
    else if ((data.event === 'autosave' || data.event === 'save') && typeof data.xml === 'string') await save(data.xml);
    else if (data.event === 'export' && exportId) {
      const ident = exportId; exportId = null; clearTimeout(exportTimer);
      await api('export', {id: ident, data: data.data});
      message(`${name} · экспорт выполнен`);
    } else if (data.error && exportId) {
      const ident = exportId; exportId = null; clearTimeout(exportTimer);
      await api('export', {id: ident, error: String(data.error)});
    }
  } catch (error) { message(error.message, true); }
});
async function poll() {
  if (loaded && !busy) {
    try {
      const data = await api('document');
      if (data.revision !== revision && !conflict && pending === null && unsaved === null) load(data);
      for (const command of data.commands) {
        if (exportId) {
          await api('export', {id: command.id, error: 'Another export is in progress. Retry.'});
          continue;
        }
        exportId = command.id;
        exportTimer = setTimeout(async () => {
          if (exportId !== command.id) return;
          exportId = null;
          try { await api('export', {id: command.id, error: 'Editor export timed out'}); } catch { /* MCP request already expired */ }
        }, 25000);
        send({action: 'export', format: command.format, xml: command.xml, border: 16, scale: 1, background: '#ffffff', transparent: false});
      }
    } catch (error) { message(`Нет связи с локальным сервером: ${error.message}`, true); }
  }
  setTimeout(poll, 1000);
}
document.getElementById('reload').addEventListener('click', async () => {
  if (busy) return;
  if (unsaved !== null && !confirm('Загрузить файл с диска и отбросить несохранённые правки?')) return;
  try {
    const data = await api('document');
    pending = null; unsaved = null; conflict = false; recovery.classList.remove('visible'); load(data);
  } catch (error) { message(error.message, true); }
});
recovery.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([unsaved || pending || ''], {type: 'application/xml'}));
  const link = document.createElement('a'); link.href = url; link.download = `unsaved-${name || 'diagram.drawio'}`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener('beforeunload', event => { if (unsaved !== null) { event.preventDefault(); event.returnValue = ''; } });
if (!session || !token) message('Откройте полный URL, который вернул open_editor.', true);
else {
  frame.src = '/drawio/index.html?embed=1&proto=json&offline=1&local=1&https=0&ui=kennedy&lang=ru&libraries=1&noSaveBtn=0&saveAndExit=0';
  poll();
}
