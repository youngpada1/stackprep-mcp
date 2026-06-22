# CLAUDE.md — stackprep-pro

Rules for working on this repo. **Do NOT violate these. Do NOT touch things that already work.**

## Golden rule

- **If something works, do NOT change it.** No "improvements", no refactors, no edits to working code. Only touch what is explicitly broken and being fixed.
- Always **follow the skill files** in `src/stackprep_pro/skills/`. The skill is the source of truth for behavior. Never invent a flow that contradicts the skill.

## Startup / session flow (MUST follow exactly)

1. When the MCP starts, **ask the user in plain human language**: "Are you prepping for a technical interview or a certification exam?"
2. **Only after** the user picks interview or certification:
   - If saved sessions exist for that mode, offer to **continue a saved session** (shown by the **name the user gave it**) or **start a new one**.
   - If none exist, just start a new session.
3. **Never expose backend tool names** to the user (no "list_sessions", "start_session", "list_study_packs", etc.). Use natural language only.
4. **Never auto-call** `list_sessions` or `list_study_packs` on startup. Call them silently in the background **only** when the user explicitly asks to continue/load.

## Certification exam version

- **Never hardcode exam versions** (e.g. do NOT hardcode "SnowPro Core = COF-C03"). It must work for **ANY** certification.
- Always pull the **latest exam version** dynamically (web search / latest official exam guide), exactly as the original skill does.
- **`cert_name` must be passed exactly as the user typed it.** Never modify, correct, or substitute it from training data (e.g. do NOT turn COF-C03 into COF-C02).

## Study pack

- The user **must be able to name** the study pack when saving it.
- Study pack format is **markdown, NOT JSON**. For each topic: official docs link (or community source like Reddit/Discord/LinkedIn if no official docs exist — e.g. niche certs like NVIDIA Agentic AI), best video resource, and a 2–3 sentence summary. Include percentages/scores and links as the original skill does.
- Never fabricate documentation URLs. Only real, publicly accessible links.

## Versioning & publishing

- This package publishes to **PyPI** as `stackprep-pro` via **GitHub Actions** on push to `main` (`.github/workflows/publish.yml`).
- **The human bumps the version in `pyproject.toml` and commits it.** The workflow does **NOT** auto-commit or auto-bump — it only reads the version, tags it, and publishes.
- Every code change that ships needs a **version bump** (PyPI rejects re-publishing an existing version).
- After publishing, to test the new version: `uv cache clean`, then restart the MCP client (uvx caches old versions).
- `git pull` is set to rebase in this repo. If branches diverge, `git pull --rebase`.

## Commit messages

- **ALWAYS give a commit title after making any change.** Every time you edit files, end your response with a single concise conventional-commit title — never skip it, never make the user ask for it.
- Do not commit/push unless explicitly asked.
