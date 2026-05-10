# iclone-mcp

MCP server that connects [Claude Code](https://claude.ai/code) to [iClone 8](https://www.reallusion.com/iclone/) via a lightweight Python bridge.

## Design Philosophy

**Thin bridge, not a wrapper.**

Rather than exposing each iClone API call as a separate MCP tool, this project gives Claude a single `execute_python` tool that sends arbitrary [RLPy](https://wiki.reallusion.com/IC8_Python_API) code directly into iClone's Python environment. This keeps the server minimal, requires no updates when the iClone API changes, and lets Claude reason about what code to write using the bundled reference manual.

**Two-layer architecture:**

```
Claude Code
    │  MCP (stdio)
    ▼
mcp_server/server.py        ← FastMCP, runs outside iClone
    │  JSON over TCP (localhost:54321)
    ▼
plugin/tcp_server.py        ← TCP server, runs inside iClone
    │
    ▼
plugin/executor.py          ← exec() in iClone's Python env (RLPy available)
```

**stdlib-only inside iClone.** The plugin uses only `socket`, `threading`, and `json` — no pip install required inside iClone's sandboxed Python.

**Offline reference manual.** `scripts/build_manual.py` scrapes the IC8 Python API wiki once and stores all 70 class pages in `manual/index.json`. Claude can look up any RLPy class without web access during a session.

## Requirements

- iClone 8 with Python scripting enabled
- Python 3.10+ (outside iClone, for the MCP server)
- [mcp](https://pypi.org/project/mcp/) (`pip install mcp`)

## Setup

### 1. Install the iClone plugin

Copy the `plugin/` folder contents to your iClone custom script directory, then load `main.py` as a plugin. A dialog confirms the server started on `localhost:54321`.

### 2. Register the MCP server with Claude Code

```bash
claude mcp add iclone python C:\path\to\iclone-mcp\mcp_server\server.py
```

### 3. Use it

Open a Claude Code session in any project. The following tools are available:

| Tool | Description |
|---|---|
| `execute_python(code)` | Run RLPy code inside iClone |
| `get_screenshot()` | Capture the iClone viewport |
| `get_manual_index()` | List all 70 RLPy API classes |
| `get_manual_entry(name)` | Full reference for a class (e.g. `Scene/RIAvatar`) |
| `search_manual(keyword)` | Search across all reference pages |

## Rebuilding the manual

```bash
python scripts/build_manual.py
```

Fetches all pages from https://wiki.reallusion.com/IC8_Python_API and writes `manual/index.json`.

## License

MIT
