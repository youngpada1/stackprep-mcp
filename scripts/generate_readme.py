#!/usr/bin/env python3
"""Auto-generates README.md from pyproject.toml, server tools, and skills files.
Run directly or via the pre-commit hook.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_meta() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]


def get_tools() -> list[dict]:
    src = (ROOT / "src" / "stackprep_mcp" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tools = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "tool"
                ):
                    doc = ast.get_docstring(node) or ""
                    first_line = doc.split("\n")[0].strip() if doc else ""
                    args = [a.arg for a in node.args.args if a.arg != "self"]
                    tools.append({"name": node.name, "doc": first_line, "args": args})
    return tools


def get_skills() -> list[dict]:
    skills_dir = ROOT / "src" / "stackprep_mcp" / "skills"
    skills = []
    for f in sorted(skills_dir.glob("*.md")):
        lines = f.read_text(encoding="utf-8").splitlines()
        title = next((l.lstrip("# ") for l in lines if l.startswith("# ")), f.stem)
        desc = next(
            (l for l in lines if l and not l.startswith("#") and not l.startswith("---") and not l.startswith("name:")),
            "",
        )
        skills.append({"mode": f.stem, "title": title, "desc": desc})
    return skills


def generate() -> str:
    meta = get_meta()
    tools = get_tools()
    skills = get_skills()

    tools_rows = ""
    for t in tools:
        args = ", ".join(f"`{a}`" for a in t["args"])
        tools_rows += f"| `{t['name']}` | {t['doc']} | {args} |\n"

    skills_rows = ""
    for s in skills:
        skills_rows += f"| `{s['mode']}` | {s['desc']} |\n"

    return f"""# {meta["name"]}

> {meta["description"]}

Works with any MCP-compatible client: **Claude Code**, **Cursor**, **Cline**, **Windsurf**, **Continue.dev**, **Codex CLI**, and more. No API key required — your existing AI subscription does the work.

---

## What it does

stackprep-mcp is a pure state-management MCP server. It tracks your session and study packs on disk; your AI client (Claude, Cursor, Codex, etc.) handles all the question generation and scoring logic using the skill rules returned at session start.

- One question at a time — interview or certification mode
- Instant scoring with doc links after every answer
- Auto-detects wrong/partial answers and builds a named study pack
- Sessions and study packs saved to disk — resume anytime, sync via iCloud
- Resume in-progress sessions across conversations or devices

---

## Install

Clone the repo and install dependencies with `uv`:

```bash
git clone https://github.com/youngpada1/stackprep-mcp
cd stackprep-mcp
uv sync
```

> Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

---

## Configure your MCP client

### Claude Code

Create `.mcp.json` in your project root:

```json
{{
  "mcpServers": {{
    "stackprep": {{
      "command": "uv",
      "args": ["run", "--directory", "/path/to/stackprep-mcp", "stackprep-mcp"]
    }}
  }}
}}
```

### Cursor

Create `~/.cursor/mcp.json`:

```json
{{
  "mcpServers": {{
    "stackprep": {{
      "command": "uv",
      "args": ["run", "--directory", "/path/to/stackprep-mcp", "stackprep-mcp"]
    }}
  }}
}}
```

Then open Cursor → **Cmd+Shift+J** → MCP tab — stackprep should appear with a green dot.

### Codex CLI

Add to `~/.codex/config.yaml`:

```yaml
mcpServers:
  stackprep:
    command: uv
    args:
      - run
      - --directory
      - /path/to/stackprep-mcp
      - stackprep-mcp
```

Replace `/path/to/stackprep-mcp` with the absolute path to the cloned repo.

---

## Study pack storage

Study packs and sessions are saved to `~/.stackprep/` by default.

**Sync across devices with iCloud** (recommended on macOS):

```bash
# Add to ~/.zshrc or ~/.zprofile
export STACKPREP_PACKS_DIR="$HOME/Documents/stackprep-packs"
```

`~/Documents` is synced to iCloud by default on macOS (requires iCloud Drive > Desktop & Documents enabled). Your packs will be available on any Mac signed into your Apple ID — and readable via the Files app on iPhone.

**Custom path:**

```bash
export STACKPREP_PACKS_DIR="/path/to/your/folder"
```

Point this at any Dropbox, Google Drive, or OneDrive folder for cross-platform sync.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `STACKPREP_PACKS_DIR` | `~/.stackprep` | Root directory for packs and sessions. |

---

## Skills (modes)

| Mode | Description |
|---|---|
{skills_rows}
---

## Tools

| Tool | Description | Args |
|---|---|---|
{tools_rows}
---

## Session flow

**Certification:**
```
list_sessions()                                          ← always called first
→ start_session(mode="certification", cert_name="AWS SAA-C03")
→ [AI generates questions one at a time]
→ submit_answer(session_id, result="correct"|"partial"|"incorrect", question="...")
→ ... repeat ...
→ end_session(session_id)
→ save_study_pack(session_id, name="aws-saa-week1", content="...")
```

**Interview:**
```
list_sessions()                                          ← always called first
→ start_session(mode="interview", cv="...", jd="...")
→ [AI generates questions one at a time]
→ submit_answer(session_id, result="correct"|"partial"|"incorrect", question="...")
→ ... repeat ...
→ end_session(session_id)
→ save_study_pack(session_id, name="python-interview-june", content="...")
```

**Resuming a session:**
```
list_sessions()                → shows in-progress sessions
→ resume_session(session_id)  → loads state + skill rules, continues where you left off
```

**Loading a saved study pack:**
```
list_study_packs()
→ load_study_pack(name="aws-saa-week1")
```

---

## Session persistence

Every session is saved to disk on every update. At the start of each new conversation the AI automatically calls `list_sessions` and asks whether you want to resume an in-progress session or start a new one. Sessions are stored in `~/.stackprep/sessions/` (or your custom `STACKPREP_PACKS_DIR`).

---

## Also available as a Claude Code plugin

For Claude Projects or direct Claude.ai use, the behaviour rules are also available as a standalone skill file at [plugins/stackprep](https://github.com/youngpada1/stackprep/tree/main/plugins/stackprep) — no install needed.

---

## Contributing / Development

```bash
git clone https://github.com/youngpada1/stackprep-mcp
cd stackprep-mcp

# Install dependencies
uv sync

# Activate the pre-commit hook (auto-regenerates README on every commit)
git config core.hooksPath .githooks

# Run the server locally
uv run stackprep-mcp
```

The README is auto-generated from `server.py` tool definitions and the skills files in `src/stackprep_mcp/skills/`.
To regenerate manually:

```bash
uv run python scripts/generate_readme.py
```

---

## License

MIT — [Flavia Fauconnet](https://github.com/flavsferr)
"""


if __name__ == "__main__":
    readme = generate()
    out = ROOT / "README.md"
    out.write_text(readme, encoding="utf-8")
    print(f"README.md generated → {out}")
