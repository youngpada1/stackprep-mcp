# stackprep-mcp

> stackprep as an MCP server — interview & certification prep for any AI client

Works with any MCP-compatible client: **Claude Desktop**, **Cursor**, **Cline**, **Windsurf**, **Continue.dev**, and more.

---

## What it does

stackprep-mcp is an MCP server that turns any AI client into an adaptive technical interview and certification prep coach.

- One question at a time — interview or certification mode
- Instant scoring with doc links after every answer
- Auto-detects wrong answers and builds a named study pack
- Study packs saved to disk — resume tomorrow, sync via iCloud

---

## Install

```bash
uvx stackprep-mcp
```

Or with pip:

```bash
pip install stackprep-mcp
```

---

## Configure your MCP client

Add to your client's MCP config (e.g. `~/.claude/mcp.json` for Claude Desktop, `.cursor/mcp.json` for Cursor):

```json
{
  "mcpServers": {
    "stackprep": {
      "command": "uvx",
      "args": ["stackprep-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-..."
      }
    }
  }
}
```

Get a free OpenRouter API key at [openrouter.ai](https://openrouter.ai).

---

## Study pack storage

Study packs are saved to `~/.stackprep/packs/` by default.

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
| `OPENROUTER_API_KEY` | — | Required. Your OpenRouter API key. |
| `STACKPREP_MODEL` | `anthropic/claude-sonnet-4.5` | Any model slug supported by OpenRouter. |
| `STACKPREP_PACKS_DIR` | `~/.stackprep` | Root directory for packs and sessions. |

**Switch model:**

```bash
# Use GPT-4o
export STACKPREP_MODEL="openai/gpt-4o"

# Use Gemini 2.5 Pro
export STACKPREP_MODEL="google/gemini-2.5-pro"
```

---

## Skills (modes)

| Mode | Description |
|---|---|
| `certification` | description: Certification prep skill for the stackprep MCP server. Activated when mode is "certification". Drives question generation, scoring, adaptive difficulty, and study pack creation. |
| `interview` | description: Interview prep skill for the stackprep MCP server. Activated when mode is "interview". Drives question generation, scoring, adaptive difficulty, and study pack creation. |

---

## Tools

| Tool | Description | Args |
|---|---|---|
| `start_session` | Start a new stackprep session. | `mode`, `cert_name`, `cv`, `jd`, `extra_topics` |
| `next_question` | Generate the next question for a session. | `session_id` |
| `submit_answer` | Submit an answer to the current question and receive scoring. | `session_id`, `answer` |
| `flag_for_study` | Manually flag the last question for the study pack. | `session_id` |
| `end_session` | End the session and receive a final study plan. Study pack is always offered. | `session_id` |
| `save_study_pack` | Generate and save a named study pack to disk. | `session_id`, `name`, `extra_topics` |
| `list_study_packs` | List all saved study packs. |  |
| `load_study_pack` | Load a previously saved study pack by name. | `name` |

---

## Session flow

**Certification:**
```
start_session(mode="certification", cert_name="AWS SAA-C03")
→ next_question(session_id)
→ submit_answer(session_id, answer="b")
→ ... repeat ...
→ end_session(session_id)
→ save_study_pack(session_id, name="aws-saa-week1")
```

**Interview:**
```
start_session(mode="interview", cv="...", jd="...")
→ next_question(session_id)
→ submit_answer(session_id, answer="A cache-aside pattern means...")
→ ... repeat ...
→ end_session(session_id)
→ save_study_pack(session_id, name="python-interview-june")
```

**Coming back tomorrow:**
```
list_study_packs()
→ load_study_pack(name="aws-saa-week1")
```

---

## Session persistence

Active sessions are saved to disk automatically. If your MCP client restarts or you switch devices (with iCloud sync enabled), the session is restored when you next call `next_question` or `submit_answer` with the same session ID.

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
To update the README manually at any time:

```bash
uv run python scripts/generate_readme.py
```

---

## License

MIT — [Flavia Fauconnet](https://github.com/flavsferr)
