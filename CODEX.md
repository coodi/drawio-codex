# draw.io for Codex

This fork adds a local Codex plugin to the original draw.io source tree.
The integration lives in `codex/`; the upstream web editor is unchanged.

## Install the packaged release

Download `drawio-codex-0.1.0.zip` from
[the Codex plugin release](https://github.com/coodi/drawio-codex/releases/tag/codex-v0.1.0),
extract it, open the extracted `drawio-codex` directory and run:

```bash
codex plugin marketplace add .
codex plugin add drawio@drawio-local
```

Requirements: Python 3.10+ and Codex with local Agent Plugins support.
Open a new Codex chat after installation. Ask it to use drawio to create a
client → API → database diagram and open the editor beside the chat.

## Develop from this branch

```bash
git clone --branch codex/drawio-plugin https://github.com/coodi/drawio-codex.git
cd drawio-codex
python3 codex/plugins/drawio/scripts/fetch-source.py
codex plugin marketplace add .
codex plugin add drawio@drawio-local
python3 -m unittest discover -s codex/tests -v
```

The download script fetches the pinned official webapp sources. The plugin
includes five MCP tools: create, read, write, open editor and export SVG/PNG.
The editor runs on localhost and saves to local `.drawio` files. Exports require
an open editor tab. No API key is needed.

See [the full Russian guide](codex/README.md) for building the standalone ZIP,
CLI use, tests, source provenance and limitations. Integration code and upstream
source retain the Apache-2.0 license and their existing notices.
