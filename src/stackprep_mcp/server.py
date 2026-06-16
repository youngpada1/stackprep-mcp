from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stackprep")

SKILLS_DIR = Path(__file__).parent / "skills"

_sessions: dict[str, dict[str, Any]] = {}


# ── Storage ────────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    env = os.environ.get("STACKPREP_PACKS_DIR")
    d = Path(env) if env else Path.home() / ".stackprep"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _packs_dir() -> Path:
    d = _data_dir() / "packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sessions_dir() -> Path:
    d = _data_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _persist_session(session_id: str) -> None:
    path = _sessions_dir() / f"{session_id}.json"
    path.write_text(json.dumps(_sessions[session_id], indent=2, ensure_ascii=False), encoding="utf-8")


def _restore_session(session_id: str) -> dict | None:
    path = _sessions_dir() / f"{session_id}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        _sessions[session_id] = data
        return data
    return None


def _delete_session(session_id: str) -> None:
    path = _sessions_dir() / f"{session_id}.json"
    if path.exists():
        path.unlink()
    _sessions.pop(session_id, None)


# ── Skill loading ──────────────────────────────────────────────────────────────

def _load_skill(mode: str) -> str:
    skill_file = SKILLS_DIR / f"{mode}.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return ""


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def start_session(
    mode: str,
    cert_name: str = "",
    cv: str = "",
    jd: str = "",
    extra_topics: str = "",
) -> str:
    """Start a new stackprep session. Returns a session ID and the skill rules for the AI to follow.

    Args:
        mode: "interview" or "certification"
        cert_name: For certification mode — the exam name (e.g. "AWS SAA-C03")
        cv: For interview mode — the user's CV/resume text
        jd: For interview mode — the job description text
        extra_topics: Optional comma-separated extra topics to focus on
    """
    if mode not in ("interview", "certification"):
        return "ERROR: mode must be 'interview' or 'certification'"
    if mode == "certification" and not cert_name:
        return "ERROR: cert_name is required for certification mode"
    if mode == "interview" and not (cv and jd):
        return "ERROR: cv and jd are required for interview mode"

    session_id = secrets.token_hex(6)

    _sessions[session_id] = {
        "mode": mode,
        "cert_name": cert_name,
        "extra_topics": extra_topics,
        "q_num": 0,
        "score": {"correct": 0, "partial": 0, "incorrect": 0, "total": 0},
        "auto_flagged": [],
        "flagged": [],
        "ended": False,
        "all_flagged": [],
    }
    _persist_session(session_id)

    skill = _load_skill(mode)
    context_lines = [f"Session ID: {session_id}", f"Mode: {mode}"]
    if cert_name:
        context_lines.append(f"Certification: {cert_name}")
    if extra_topics:
        context_lines.append(f"Extra topics: {extra_topics}")
    if cv:
        context_lines.append(f"\n--- CV ---\n{cv}")
    if jd:
        context_lines.append(f"\n--- Job description ---\n{jd}")

    return "\n".join([
        "=== STACKPREP SESSION STARTED ===",
        "\n".join(context_lines),
        "\n=== SKILL RULES (follow these exactly) ===",
        skill,
    ])


@mcp.tool()
def submit_answer(session_id: str, result: str, question: str = "") -> str:
    """Record the result of an answered question.

    Args:
        session_id: The session ID
        result: "correct", "partial", or "incorrect"
        question: The question text (used to build the study pack)
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    result = result.lower().strip()
    if result not in ("correct", "partial", "incorrect"):
        return "ERROR: result must be 'correct', 'partial', or 'incorrect'"

    session["q_num"] += 1
    session["score"]["total"] += 1
    q_num = session["q_num"]
    snippet = question[:200] if question else f"Q{q_num}"

    if result == "correct":
        session["score"]["correct"] += 1
    elif result == "partial":
        session["score"]["partial"] += 1
        session["score"]["correct"] += 1
        session["auto_flagged"].append(f"Q{q_num}: {snippet}")
    elif result == "incorrect":
        session["score"]["incorrect"] += 1
        session["auto_flagged"].append(f"Q{q_num}: {snippet}")

    _persist_session(session_id)

    score = session["score"]
    return f"Recorded Q{q_num}: {result}. Score: {score['correct']}/{score['total']}"


@mcp.tool()
def flag_for_study(session_id: str, question: str = "") -> str:
    """Manually flag the current question for the study pack.

    Args:
        session_id: The session ID
        question: The question text to flag
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    q_num = session["q_num"]
    snippet = question[:200] if question else f"Q{q_num}"
    entry = f"Q{q_num}: {snippet}"
    if entry not in session["flagged"]:
        session["flagged"].append(entry)
    _persist_session(session_id)
    return f"Flagged Q{q_num} for study. Total flagged: {len(session['flagged'])}."


@mcp.tool()
def end_session(session_id: str) -> str:
    """End the session. Returns the score and flagged topics so the AI can generate a study plan and study pack.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    all_flagged = list(dict.fromkeys(session["auto_flagged"] + session["flagged"]))
    session["ended"] = True
    session["all_flagged"] = all_flagged
    _persist_session(session_id)

    score = session["score"]
    topics_list = "\n".join(f"  • {t}" for t in all_flagged) if all_flagged else "  (none — full score!)"

    return "\n".join([
        "=== SESSION ENDED ===",
        f"Score: {score['correct']}/{score['total']} "
        f"({score['incorrect']} incorrect, {score['partial']} partial)",
        "",
        "Auto-detected study topics:",
        topics_list,
        "",
        "Generate a Study Plan now (see skill rules), then ask the user:",
        '  "Want to add any extra topics to your study pack before I save it?"',
        f"Then call save_study_pack(session_id='{session_id}', name=<chosen name>, content=<generated pack>)",
    ])


@mcp.tool()
def save_study_pack(session_id: str, name: str, content: str) -> str:
    """Save the study pack content to disk.

    Args:
        session_id: The session ID (must have called end_session first)
        name: Slug name for this pack, e.g. "aws-saa-week1" or "python-interview-june"
        content: The full study pack markdown generated by the AI
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."
    if not session.get("ended"):
        return "ERROR: Call end_session first before saving a study pack."

    safe_name = re.sub(r"[^a-z0-9_-]", "-", name.lower().strip())
    if not safe_name:
        return "ERROR: Pack name must contain at least one letter or number."

    packs = _packs_dir()
    pack_json_path = packs / f"{safe_name}.json"
    pack_md_path = packs / f"{safe_name}.md"

    pack_data = {
        "name": safe_name,
        "mode": session["mode"],
        "score": session["score"],
        "topics": session.get("all_flagged", []),
        "raw_markdown": content,
    }
    pack_json_path.write_text(json.dumps(pack_data, indent=2, ensure_ascii=False), encoding="utf-8")
    pack_md_path.write_text(f"# Study Pack: {safe_name}\n\n{content}", encoding="utf-8")

    _delete_session(session_id)

    return (
        f"Study pack '{safe_name}' saved.\n"
        f"  JSON → {pack_json_path}\n"
        f"  Markdown → {pack_md_path}"
    )


@mcp.tool()
def list_study_packs() -> str:
    """List all saved study packs."""
    packs = _packs_dir()
    files = sorted(packs.glob("*.json"))
    if not files:
        return f"No study packs saved yet. Packs are stored in: {packs}"

    lines = [f"Saved study packs ({len(files)}) — {packs}\n"]
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            mode = data.get("mode", "?")
            score = data.get("score", {})
            lines.append(f"  • {f.stem}  [{mode}]  score: {score.get('correct','?')}/{score.get('total','?')}")
        except Exception:
            lines.append(f"  • {f.stem}")
    return "\n".join(lines)


@mcp.tool()
def load_study_pack(name: str) -> str:
    """Load a previously saved study pack by name.

    Args:
        name: The pack name (e.g. "aws-saa-week1"). Use list_study_packs to see available packs.
    """
    safe_name = re.sub(r"[^a-z0-9_-]", "-", name.lower().strip())
    pack_path = _packs_dir() / f"{safe_name}.json"
    if not pack_path.exists():
        return f"ERROR: No study pack named '{safe_name}' found. Use list_study_packs to see available packs."

    data = json.loads(pack_path.read_text(encoding="utf-8"))
    return data.get("raw_markdown", json.dumps(data, indent=2))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
