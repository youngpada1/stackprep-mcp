from __future__ import annotations

import json
import os
import re
import secrets
import textwrap
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stackprep")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("STACKPREP_MODEL", "anthropic/claude-sonnet-4.5")
SKILLS_DIR = Path(__file__).parent / "skills"

_sessions: dict[str, dict[str, Any]] = {}


# ── Storage helpers ────────────────────────────────────────────────────────────

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
    session = _sessions[session_id]
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


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
    return _fallback_prompt()


def _fallback_prompt() -> str:
    return """You are an expert technical interviewer and certification coach delivering
questions ONE AT A TIME in an interactive session.

Each turn you will either:
1. Receive "NEXT_QUESTION" — generate exactly ONE new question.
2. Receive the user's answer — score it immediately.

Scoring format:
RESULT: ✅ Correct  OR  RESULT: ⚠️ Partial  OR  RESULT: ❌ Incorrect
EXPLANATION: <2 sentences max>
DOCS: <Title>: <url>
"""


# ── LLM call ───────────────────────────────────────────────────────────────────

async def _call_llm(messages: list[dict], system: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set.")

    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "system", "content": system}] + messages,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/youngpada1/stackprep",
        "X-Title": "stackprep-mcp",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


# ── Session init helpers ───────────────────────────────────────────────────────

def _build_initial_message(
    mode: str, cert_name: str, cv: str, jd: str, extra_topics: str
) -> str:
    extra = f"\n\nExtra topics to focus on: {extra_topics}" if extra_topics else ""
    if mode == "certification":
        return textwrap.dedent(f"""
            The user wants to prepare for the following certification exam:

            {cert_name}{extra}

            Use the LATEST official exam guide, domains, and weighting for this certification.
            If official documentation is sparse, draw from community exam reports (Reddit, Discord, LinkedIn).
            Do NOT ask for a CV or job description — this is pure exam prep.
            Give a 2-line summary of the exam structure and key domains, then stop.
        """).strip()
    else:
        return textwrap.dedent(f"""
            Analyse the CV and job description below. Give a 3-line analysis
            (seniority level, key domains, top skill gaps), then stop.

            --- CV ---
            {cv}

            --- Job description ---
            {jd}{extra}
        """).strip()


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def start_session(
    mode: str,
    cert_name: str = "",
    cv: str = "",
    jd: str = "",
    extra_topics: str = "",
) -> str:
    """Start a new stackprep session.

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
    system = _load_skill(mode)
    initial_msg = _build_initial_message(mode, cert_name, cv, jd, extra_topics)

    messages: list[dict] = [{"role": "user", "content": initial_msg}]
    analysis = await _call_llm(messages, system)
    messages.append({"role": "assistant", "content": analysis})

    _sessions[session_id] = {
        "mode": mode,
        "messages": messages,
        "q_num": 0,
        "score": {"correct": 0, "total": 0},
        "flagged": [],
        "auto_flagged": [],
        "last_question": "",
        "ended": False,
        "all_flagged": [],
    }
    _persist_session(session_id)

    return f"Session started. ID: {session_id}\n\n{analysis}"


@mcp.tool()
async def next_question(session_id: str) -> str:
    """Generate the next question for a session.

    Args:
        session_id: The session ID returned by start_session
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'. Call start_session first."

    session["q_num"] += 1
    msgs = session["messages"]
    msgs.append({"role": "user", "content": "NEXT_QUESTION"})

    system = _load_skill(session["mode"])
    question = await _call_llm(msgs, system)
    msgs.append({"role": "assistant", "content": question})
    session["last_question"] = question
    _persist_session(session_id)

    return f"Q{session['q_num']}:\n\n{question}"


@mcp.tool()
async def submit_answer(session_id: str, answer: str) -> str:
    """Submit an answer to the current question and receive scoring.

    Args:
        session_id: The session ID
        answer: The user's answer (letter for cert mode, free text for interview mode)
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."
    if not session["last_question"]:
        return "ERROR: No question has been asked yet. Call next_question first."

    msgs = session["messages"]
    msgs.append({"role": "user", "content": f"My answer: {answer}"})

    system = _load_skill(session["mode"])
    result = await _call_llm(msgs, system)
    msgs.append({"role": "assistant", "content": result})

    session["score"]["total"] += 1
    q_num = session["q_num"]
    snippet = session["last_question"][:200]

    if "RESULT: ✅" in result:
        session["score"]["correct"] += 1
    elif "RESULT: ⚠️" in result:
        session["score"]["correct"] += 1
        session["auto_flagged"].append(f"Q{q_num}: {snippet}")
    elif "RESULT: ❌" in result:
        session["auto_flagged"].append(f"Q{q_num}: {snippet}")

    _persist_session(session_id)

    score = session["score"]
    return f"{result}\n\nScore so far: {score['correct']}/{score['total']}"


@mcp.tool()
async def flag_for_study(session_id: str) -> str:
    """Manually flag the last question for the study pack.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    q_num = session["q_num"]
    snippet = session["last_question"][:200]
    entry = f"Q{q_num}: {snippet}"
    if entry not in session["flagged"]:
        session["flagged"].append(entry)
    _persist_session(session_id)
    return f"Flagged Q{q_num} for study. Total manually flagged: {len(session['flagged'])}."


@mcp.tool()
async def end_session(session_id: str) -> str:
    """End the session and receive a final study plan. Study pack is always offered.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    msgs = session["messages"]
    msgs.append({
        "role": "user",
        "content": (
            "I'm done for today. Please give me a final Study Plan:\n"
            "- Topics mastered (≥ 80% correct)\n"
            "- Topics to review (50–79%)\n"
            "- Topics to focus on (< 50%)\n"
            "- 3–5 concrete study actions per weak area."
        ),
    })
    system = _load_skill(session["mode"])
    plan = await _call_llm(msgs, system)
    score = session["score"]

    all_flagged = list(dict.fromkeys(session["auto_flagged"] + session["flagged"]))
    session["ended"] = True
    session["all_flagged"] = all_flagged
    _persist_session(session_id)

    if all_flagged:
        topics_preview = "\n".join(f"  • {t[:80]}" for t in all_flagged)
        pack_prompt = (
            f"\n\n---\n\n**Study pack** — {len(all_flagged)} topic(s) auto-detected:\n"
            f"{topics_preview}\n\n"
            "Want to add any extra topics? "
            "Call `save_study_pack` with a name (e.g. `aws-saa-week1`) and optional `extra_topics` to generate and save it."
        )
    else:
        pack_prompt = (
            "\n\n---\n\n**Study pack** — You answered everything correctly! "
            "A study pack is still available to reinforce these topics. "
            "Call `save_study_pack` with a name to generate and save it."
        )

    return f"{plan}\n\nFinal score: {score['correct']}/{score['total']}{pack_prompt}"


@mcp.tool()
async def save_study_pack(session_id: str, name: str, extra_topics: str = "") -> str:
    """Generate and save a named study pack to disk.

    Args:
        session_id: The session ID (call end_session first)
        name: Slug name for this pack, e.g. "aws-saa-week1" or "python-interview-june"
        extra_topics: Optional comma-separated extra topics to include beyond auto-detected ones
    """
    session = _sessions.get(session_id) or _restore_session(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."
    if not session.get("ended"):
        return "ERROR: Call end_session first before saving a study pack."

    safe_name = re.sub(r"[^a-z0-9_-]", "-", name.lower().strip())
    if not safe_name:
        return "ERROR: Pack name must contain at least one letter or number."

    all_flagged = session.get("all_flagged", [])
    extras = [t.strip() for t in extra_topics.split(",") if t.strip()] if extra_topics else []

    topic_parts: list[str] = []
    if all_flagged:
        topic_parts.append("Topics from session:\n" + "\n".join(f"- {t}" for t in all_flagged))
    if extras:
        topic_parts.append("Extra topics:\n" + "\n".join(f"- {t}" for t in extras))
    if not topic_parts:
        topic_parts.append("General review of all topics covered in this session.")

    prompt = (
        "Generate a Study Pack for the following topics. "
        "Return a JSON block (```json ... ```) then a human-readable markdown summary.\n\n"
        + "\n\n".join(topic_parts)
        + "\n\nJSON schema (array of topics):\n"
        '[{"topic":"","official_docs":[{"title":"","url":""}],'
        '"videos":[{"title":"","url":""}],'
        '"exam_prep":[{"title":"","url":""}],'
        '"summary":""}]\n\n'
        "Use only real, publicly accessible URLs. Never fabricate links."
    )

    system = _load_skill(session["mode"])
    raw = await _call_llm([{"role": "user", "content": prompt}], system)

    json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    topics_json: list[dict] = []
    if json_match:
        try:
            topics_json = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    packs = _packs_dir()
    pack_json_path = packs / f"{safe_name}.json"
    pack_md_path = packs / f"{safe_name}.md"

    pack_data = {
        "name": safe_name,
        "mode": session["mode"],
        "score": session["score"],
        "topics": topics_json,
        "raw_markdown": raw,
    }
    pack_json_path.write_text(json.dumps(pack_data, indent=2, ensure_ascii=False), encoding="utf-8")
    pack_md_path.write_text(f"# Study Pack: {safe_name}\n\n{raw}", encoding="utf-8")

    _delete_session(session_id)

    return (
        f"Study pack '{safe_name}' saved.\n"
        f"  JSON → {pack_json_path}\n"
        f"  Markdown → {pack_md_path}\n\n"
        f"{raw}"
    )


@mcp.tool()
async def list_study_packs() -> str:
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
async def load_study_pack(name: str) -> str:
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
