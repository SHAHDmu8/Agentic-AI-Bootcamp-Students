# Module 5B — Agent Skills

> **The one thing to leave with:** a skill is how an agent knows *how to do the
> job well*. MCP was how it reaches the tools.

Yesterday you connected an agent to a server somebody else wrote. Today you
package **judgement** the same way — and watch a skill start other agents.

---

## Read this before you touch anything

### 1. Use the right Python

Same environment as Module 5. **Python 3.12.**

```powershell
.venv\Scripts\python.exe --version      # expect 3.12.x
```

### 2. Install

```powershell
.venv\Scripts\python.exe -m pip install -r Module-05B-Agent-Skills\requirements.txt
```

Only two packages, and you already have both from Module 1.

### 3. Your `.env`

`OPENROUTER_API_KEY` at the repo root. Same key as always.

### 4. Setup check

If this prints three skills, you are ready:

```powershell
cd Module-05B-Agent-Skills\skill-runner
..\..\.venv\Scripts\python.exe skill_runner.py --list
```

---

## The module, in order

| # | folder | what you do | time |
|---|---|---|---|
| 1 | **`demos/`** | Five real, public skills. Five different shapes. Watch, then read the source. | 45 min |
| 2 | **`skill-runner/`** | Run a working skills runtime. Watch progressive disclosure pay for itself in tokens. | 30 min |
| 3 | **`skill-runner/skills/`** | Three reference skills to read and copy from. | — |
| 4 | **`scenarios/`** | Claim one of 15 scenarios. Build your skill. Show it. | 45 min |
| 5 | **`bridge-project/`** | **This week's bridge project** — forge a skill and ship it to the shared library. | ~3 h, during the week |

**Every folder has its own README. That README is your worksheet.**

---

## 🔥 This week's bridge project

**[→ bridge-project/THE-BRIEF.md](bridge-project/THE-BRIEF.md)**

Build a skill that solves a real problem *you* have, prove it works **and** that
it stays quiet when it should, then ship it to the shared library:

### **[jhf-skills.azurewebsites.net](https://jhf-skills.azurewebsites.net)**

This time you don't submit an issue — you open a **pull request**. An issue is a
conversation that gets closed; a pull request is files that get merged and stay
installable by everyone, forever. The library outlives the course.

**[→ How to upload your skill, step by step](https://github.com/Alaaldin97/Agentic-AI-Skill-Foundry/blob/main/UPLOAD-A-SKILL.md)** — includes a no-terminal route.

**Due before Session 7.**

---

Also here:

- `M5B-Learner-Handout.md` — the concepts, written down.
- `M5B-Lab-Worksheet.md` — the run order and submission rules.
- `scenarios/PICK-A-SCENARIO.html` — open in any browser to claim a scenario.

---

## The four-hour shape

| time | what |
|---|---|
| 0:00 – 0:20 | Review: the bridge project, and what MCP did *not* solve |
| 0:20 – 0:50 | The shift — from connection to competence |
| 0:50 – 1:35 | **Part 1** · five real skills, five shapes (`demos/`) |
| 1:35 – 1:45 | break |
| 1:45 – 2:15 | **Part 2** · anatomy — build one skill together |
| 2:15 – 2:45 | **Part 3** · the runner — progressive disclosure, proven (`skill-runner/`) |
| 2:45 – 3:30 | **Part 4** · claim a scenario, build it (`scenarios/`) |
| 3:30 – 3:50 | showcase — 2 minutes each |
| 3:50 – 4:00 | closing — skills that run agents |

---

## The three reference skills

Read these before writing your own. They are deliberately different shapes.

| skill | shape | the idea it carries |
|---|---|---|
| **`jhf-brief`** | instructions + script + template | Deterministic checks belong in code. The script is the referee, not the model. |
| **`repo-onboarder`** | instructions + a script that *looks* | Facts from code, prose from the model. Never let the model guess what's on disk. |
| **`lab-grader`** | instructions + **five sub-agents** | A skill can be an orchestrator. Five independent examiners, one per criterion, each with a fresh context. |

`lab-grader` grades against the same rubric we grade you with. Run it on your
own submission before you hand it in.

---

## When something breaks

| symptom | cause | fix |
|---|---|---|
| `404 ... 0 endpoints ... ZDR violation` | your model can't take tools on this account | `$env:SKILL_MODEL="openai/gpt-4.1-mini"` |
| The run hangs on a request where no skill fires | `tools=None` serialises as `"tools": null` | omit the key entirely — see the comment in `run()` |
| Garbled `â€"` in the terminal | Windows cp1252 console | already fixed in the runner; do the same in your own scripts |
| `UnicodeDecodeError` from a script | subprocess pipe defaults to cp1252 | pass `encoding="utf-8"` to `subprocess.run` |
| The skill always fires | your description says *what* it is, not *when* to use it | rewrite it as "Use when the user asks for…" |
| The skill never fires | the description uses your words, not the user's | write the symptom, not the feature |
| `ModuleNotFoundError: openai` | wrong interpreter | use `Module-02\.venv`, not the root one |

---

## What we are *not* doing today

We are not building a skill **marketplace**, and we are not wiring skills into
Claude Code or Copilot CLI. Both are real and both are twenty minutes of
plumbing once you understand the format — which is the actual goal.

The format is an open standard. Get that right and the plumbing is a detail.
