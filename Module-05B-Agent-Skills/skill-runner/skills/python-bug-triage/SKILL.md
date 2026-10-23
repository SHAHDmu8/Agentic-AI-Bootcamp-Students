---
name: python-bug-triage
description: Triage a Python or agent bug report into severity, missing facts, and the next action. Use when the user shares a traceback, failing test, crash, or "this is broken" report and needs it classified quickly.
---

# Skill: Python Bug Triage

This skill turns a noisy bug report into a clean triage note: severity, likely component, required missing information, and the next action.

## When to use this

Fires on: "this Python function is failing", "triage this bug report", "my agent crashed", "I have a traceback", "this is broken in production", "classify this error", "our API returns 500 after a request".

Does NOT fire on: "explain this repo", "write a brief", "review my PR", "help me write a cover letter", or other non-bug-report tasks. If the user is asking for general advice instead of a report triage, answer normally.

## Steps

1. Read the bug report text exactly as given by the user.
2. Call `read_resource("resources/triage-rules.md")` to load the severity and required-field rules.
3. Call `run_script("triage_bug.py", <the raw bug report>)`. The script performs the deterministic checks, counts phrases, and outputs a structured verdict.
4. If the script shows missing fields such as version, environment, expected result, steps, or reproduction, say so plainly and ask for those facts instead of guessing.
5. Write a short triage summary with four lines: severity, likely component, missing facts, and the next action.
6. Call `save_output("triage-<topic>.md", <the summary>)`.

## Rules

- Never invent a traceback, stack trace, or user environment.
- A bug report without reproduction steps is not a complete report.
- If the report is severe, say so only when the evidence matches the rule set.
- Prefer precise missing-information requests over guesses.
- Do not escalate feature requests into bug triage.
