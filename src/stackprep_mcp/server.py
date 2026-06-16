from __future__ import annotations

import json
import os
import re
import secrets
import textwrap
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stackprep")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("STACKPREP_MODEL", "anthropic/claude-sonnet-4.5")

_sessions: dict[str, dict[str, Any]] = {}


def _system_prompt() -> str:
    return """You are an expert technical interviewer and certification coach delivering
questions ONE AT A TIME in an interactive session.

## Session flow

Each turn you will either:
1. Receive "NEXT_QUESTION" — generate exactly ONE new question.
2. Receive the user's answer to the current question — score it immediately.

## Question format

Interview mode — open-ended:
Q. [Conceptual] <question text>

Certification mode — multiple choice:
Q. [Domain: <domain name>] <question text>
  a) …
  b) …
  c) …
  d) …

Do NOT include the answer in the question. Only reveal the correct answer in the EXPLANATION after the user has replied.

## Question format rules

- If a topic requires a long or detailed answer → make it **multiple choice** (a/b/c/d). Never ask open-ended questions that require essays.
- Only use open-ended format for simple, one-sentence answers (e.g. "What does X stand for?").
- Keep questions concise.
- **CRITICAL — answer position**: The correct answer MUST be placed at a genuinely random position (a, b, c, or d). Spread correct answers across all four letters throughout a session. Never default to b or c. If your last two questions shared the same correct letter, force a different one now.
- Never use "all of the above" or "none of the above" as an option unless it is the only honest way to test the concept.

## Scoring format

Keep scoring SHORT — 2 sentences max.

RESULT: ✅ Correct  OR  RESULT: ⚠️ Partial  OR  RESULT: ❌ Incorrect

EXPLANATION: <2 sentences max. What's right. If partial, one improvement tip.>

DOCS: <Title>: <url>

## Adaptive difficulty

Track what the user gets wrong and make subsequent questions harder on those topics.
Never repeat the same question in a session.

## Certifications with limited official documentation

For newer or niche certifications (e.g. NVIDIA Agentic AI, emerging vendor certs) where the official exam guide is sparse:
- Draw questions from course learning objectives and community exam reports (Reddit, Discord, LinkedIn posts from recent candidates).
- Cite community sources in DOCS when no official docs exist.
- Do NOT fabricate official documentation URLs.

## Study Pack generation

When asked to generate a Study Pack, produce a JSON block (```json … ```) then markdown.
JSON schema per topic: {"topic","official_docs":[{"title","url"}],"videos":[{"title","url"}],"exam_prep":[{"title","url"}],"summary"}
Use only real, publicly accessible URLs.
"""


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
        "HTTP-Referer": "https://github.com/youngpada1/stackprep-mcp",
        "X-Title": "stackprep-mcp",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


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
            Mode: certification
        """).strip()
    else:
        return textwrap.dedent(f"""
            Analyse the CV and job description below. Give a 3-line analysis
            (seniority level, key domains, top skill gaps), then stop.

            --- CV ---
            {cv}

            --- Job description ---
            {jd}{extra}

            Mode: interview
        """).strip()


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
        cert_name: For certification mode — the exam name (e.g. "NVIDIA Agentic AI", "AWS SAA-C03")
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
    system = _system_prompt()
    initial_msg = _build_initial_message(mode, cert_name, cv, jd, extra_topics)

    messages: list[dict] = [{"role": "user", "content": initial_msg}]
    analysis = await _call_llm(messages, system)
    messages.append({"role": "assistant", "content": analysis})

    _sessions[session_id] = {
        "mode": mode,
        "system": system,
        "messages": messages,
        "q_num": 0,
        "score": {"correct": 0, "total": 0},
        "flagged": [],
        "last_question": "",
    }

    return f"Session started. ID: {session_id}\n\n{analysis}"


@mcp.tool()
async def next_question(session_id: str) -> str:
    """Generate the next question for a session.

    Args:
        session_id: The session ID returned by start_session
    """
    session = _sessions.get(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'. Call start_session first."

    session["q_num"] += 1
    msgs = session["messages"]
    msgs.append({"role": "user", "content": "NEXT_QUESTION"})

    question = await _call_llm(msgs, session["system"])
    msgs.append({"role": "assistant", "content": question})
    session["last_question"] = question

    return f"Q{session['q_num']}:\n\n{question}"


@mcp.tool()
async def submit_answer(session_id: str, answer: str) -> str:
    """Submit an answer to the current question and receive scoring.

    Args:
        session_id: The session ID
        answer: The user's answer (letter for cert mode, free text for interview mode)
    """
    session = _sessions.get(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."
    if not session["last_question"]:
        return "ERROR: No question has been asked yet. Call next_question first."

    msgs = session["messages"]
    msgs.append({"role": "user", "content": f"My answer: {answer}"})

    result = await _call_llm(msgs, session["system"])
    msgs.append({"role": "assistant", "content": result})

    session["score"]["total"] += 1
    if "RESULT: ✅" in result or "RESULT: ⚠️" in result:
        session["score"]["correct"] += 1

    score = session["score"]
    return f"{result}\n\nScore so far: {score['correct']}/{score['total']}"


@mcp.tool()
async def flag_for_study(session_id: str) -> str:
    """Flag the last question for the study pack.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."

    q_num = session["q_num"]
    snippet = session["last_question"][:200]
    session["flagged"].append(f"Q{q_num}: {snippet}")
    return f"Flagged Q{q_num} for study. Total flagged: {len(session['flagged'])}."


@mcp.tool()
async def generate_study_pack(session_id: str) -> str:
    """Generate a study pack with resources for all flagged topics.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id)
    if not session:
        return f"ERROR: No session found with ID '{session_id}'."
    if not session["flagged"]:
        return "No topics flagged yet. Use flag_for_study after a wrong answer."

    topic_list = "\n".join(f"- {item}" for item in session["flagged"])
    prompt = (
        "Generate a Study Pack for these flagged topics. "
        "Return a JSON block (```json ... ```) then a markdown summary.\n\n"
        f"{topic_list}"
    )
    result = await _call_llm([{"role": "user", "content": prompt}], session["system"])
    session["flagged"] = []
    return result


@mcp.tool()
async def end_session(session_id: str) -> str:
    """End the session and receive a final study plan.

    Args:
        session_id: The session ID
    """
    session = _sessions.get(session_id)
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
    plan = await _call_llm(msgs, session["system"])
    score = session["score"]
    del _sessions[session_id]
    return f"{plan}\n\nFinal score: {score['correct']}/{score['total']}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
