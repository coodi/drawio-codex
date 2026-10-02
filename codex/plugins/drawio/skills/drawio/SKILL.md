---
name: drawio
description: Create, inspect, edit, and export local draw.io diagrams (.drawio), and open the original draw.io editor beside the Codex chat.
---

Use the bundled drawio MCP tools for local diagrams. They require absolute file paths and run on the user's computer with Python 3.10+. The editor is vendored from the official jgraph/drawio source, with its version pinned in vendor/drawio/source.json.

- Create with `create_diagram`: provide nodes with stable IDs and labels, plus edges referencing those IDs. Coordinates, dimensions and draw.io styles are optional. For groups, custom shapes or multiple pages, supply full `mxfile` XML instead.
- Read existing diagrams with `read_diagram`. It returns original XML, a revision hash and cells for each page; compressed pages are decoded for inspection.
- Edit the existing XML while preserving unrelated pages, styles and geometry. Submit through `write_diagram` with the revision returned by the read. If a conflict occurs, reread and reconcile with the user's current changes.
- Call `open_editor`, then open its returned URL with Codex `open_in_codex`, browser target. The original draw.io editor saves to the same local file and reloads changes made by Codex. Treat the full URL as a local session capability; don't send it to external services. The MCP process must stay alive while editing.
- For SVG or PNG, first open the editor tab and let it finish loading, then call `export_diagram` with an absolute, new output path. Export is rendered by draw.io, requires the tab to remain open, and times out after 30 seconds. Link the resulting file. There is no headless export or PDF exporter in this plugin.

If MCP tools are unavailable in the current chat, use the Python CLI at `../../scripts/drawio.py` relative to this skill directory. `call create_diagram '<JSON>'`, `call read_diagram '<JSON>'` and `call write_diagram '<JSON>'` expose the same file operations. Use `serve /absolute/path/diagram.drawio` in a persistent terminal to obtain an editor URL. `call open_editor` cannot keep a server alive. A fresh chat after plugin installation is needed to load its MCP tools.

If editor assets are missing in a source checkout, run `../../scripts/fetch-source.py` once. It downloads the pinned official source and copies its webapp into the plugin. Packaged releases include those assets. No API key is required. Advanced upstream functions that require remote storage or an export server are outside the local integration.
