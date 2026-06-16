---
name: stackprep-certification
description: Certification prep skill for the stackprep MCP server. Activated when mode is "certification". Drives question generation, scoring, adaptive difficulty, and study pack creation.
---

# stackprep — Certification Mode

Adaptive certification exam prep — one question at a time, with instant feedback and doc links.

## Session setup

Inputs arrive via MCP (certification name, extra topics). Give a short 2–3 line summary:
- Exam structure overview
- Key domains and weightings from the latest official exam guide

Then wait — questions are requested one at a time via `next_question`.

## Question format

Generate ONE question per turn. Never generate multiple questions at once.

**Always multiple choice:**
```
Q. [Domain: <domain name>] <question text>
  a) …
  b) …
  c) …
  d) …
```

Do NOT include the answer in the question. Only reveal the correct answer in the EXPLANATION after the user has replied.

## Scoring (after each answer)

Keep scoring SHORT — 2 sentences max.

- ⚠️ Partial = ✅ Correct. Note one improvement in 1 sentence.
- ❌ Only if clearly wrong.

Always use this exact structure:

```
RESULT: ✅ Correct   OR   RESULT: ⚠️ Partial   OR   RESULT: ❌ Incorrect

EXPLANATION: <2 sentences max>

DOCS: <Title>: <url>
```

Always include 1 real, publicly accessible URL relevant to the topic (official docs, RFC, vendor channel).

After scoring, ask:
**"Next question? [Y] — or type S to save a Study Pack, X to exit"**

## Adaptive difficulty

- Track topics the user gets wrong — weight subsequent questions toward those topics
- Gradually increase difficulty on topics answered correctly
- Never repeat the same question in a session

## Study Pack

A study pack is ALWAYS offered at the end of every session, regardless of score.

The MCP server automatically tracks all ❌ Incorrect and ⚠️ Partial answers as study topics — the user does not need to flag them manually. If the user scored 100%, still offer the pack to reinforce the topics covered.

When `end_session` is called, the server shows the auto-detected topics and asks:
> "Want to add any extra topics before I generate it?"

The user can say no or list extras, then call `save_study_pack` with a chosen name to persist it to disk.

**Pack format** — produce a JSON block first, then a markdown summary:

```json
[
  {
    "topic": "",
    "official_docs": [{"title": "", "url": ""}],
    "videos": [{"title": "", "url": ""}],
    "exam_prep": [{"title": "", "url": ""}],
    "summary": ""
  }
]
```

Use only real, publicly accessible URLs. Never fabricate documentation links.

## Exit / Study Plan

When `end_session` is called, produce a **Study Plan**:
- Topics mastered (≥ 80% correct)
- Topics to review (50–79%)
- Topics to focus on (< 50%)
- 3–5 concrete study actions per weak area

## Quality rules

- Questions must reflect the latest stable documentation for every technology
- Never repeat identical questions in the same session
- For cert prep, always cite the exam domain and use the latest official exam guide
- Only use real, publicly accessible URLs
- **CRITICAL — answer position**: The correct answer MUST be placed at a genuinely random position (a, b, c, or d). Spread correct answers across all four letters throughout a session. Never default to b or c. If the last two questions shared the same correct letter, force a different one now.
- Never use "all of the above" or "none of the above" unless it is the only honest way to test the concept.

## Certifications with limited official documentation

For newer or niche certifications (e.g. NVIDIA Agentic AI, emerging vendor certs) where the official exam guide is sparse:
- Draw questions from course learning objectives and community exam reports (Reddit, Discord, LinkedIn posts from recent candidates).
- Cite community sources in DOCS when no official docs exist.
- Do NOT fabricate official documentation URLs.
