# stackprep-mcp

> stackprep as an MCP server — interview & certification prep for any AI client

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
{
  "mcpServers": {
    "stackprep": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/stackprep-mcp", "stackprep-mcp"]
    }
  }
}
```

### Cursor

Create `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "stackprep": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/stackprep-mcp", "stackprep-mcp"]
    }
  }
}
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
| `certification` | description: Certification prep skill for the stackprep MCP server. Activated when mode is "certification". Drives question generation, scoring, adaptive difficulty, and study pack creation. |
| `interview` | description: Interview prep skill for the stackprep MCP server. Activated when mode is "interview". Drives question generation, scoring, adaptive difficulty, and study pack creation. |

---

## Tools

| Tool | Description | Args |
|---|---|---|
| `start_session` | Start a new stackprep session. Returns a session ID and the skill rules for the AI to follow. | `mode`, `cert_name`, `cv`, `jd`, `extra_topics` |
| `submit_answer` | Record the result of an answered question. | `session_id`, `result`, `question` |
| `flag_for_study` | Manually flag the current question for the study pack. | `session_id`, `question` |
| `end_session` | End the session. Returns the score and flagged topics so the AI can generate a study plan and study pack. | `session_id` |
| `save_study_pack` | Save the study pack content to disk. | `session_id`, `name`, `content` |
| `list_sessions` | List all saved sessions (pending and completed). |  |
| `resume_session` | Resume a previously saved session. Returns full session state and skill rules. | `session_id` |
| `list_study_packs` | List all saved study packs. |  |
| `load_study_pack` | Load a previously saved study pack by name. | `name` |

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
