# Parts 2 & 3 — The Runner: build a skill, then watch it pay for itself

Claude Code, Codex, Cursor and Copilot CLI all load skills. None of them show
you *how*. `skill_runner.py` is the same idea with the lid off — about 300
lines, no framework, and it prints its receipts every run.

---

## Run it first, understand it second

```powershell
cd Module-05B-Agent-Skills\skill-runner
..\..\.venv\Scripts\python.exe skill_runner.py --list
```

```
3 skill(s) discovered

  jhf-brief
    Produce a one-page, JHF-styled decision brief on a topic. Use when the user
    asks for a "brief", "one-pager", "exec summary" or "summary report".
    full body: ~397 tokens, loaded only on match
  ...
```

Now fire one:

```powershell
..\..\.venv\Scripts\python.exe skill_runner.py "Give me a one-page brief on agentic RAG for a CTO audience"
```

Real output from this machine:

```
REQUEST  Give me a one-page brief on agentic RAG for a CTO audience
SKILLS   3 on disk: jhf-brief, lab-grader, repo-onboarder
ROUTED   jhf-brief
  -> read_resource({'relative_path': 'resources/brief-template.md'}...)
  -> run_script({'script_name': 'format_brief.py', ...)
  -> save_output({'filename': 'brief-agentic-rag.md', ...)

PROGRESSIVE DISCLOSURE — what it actually cost
  skills on disk .............. 3
  menu shown to the router .... ~235 tokens
  if we had loaded ALL of them. ~1,481 tokens
  we actually loaded .......... ~397 tokens (jhf-brief)
  SAVED ....................... ~1,084 tokens
```

Now prove the other half — that a skill **stays out of the way**:

```powershell
..\..\.venv\Scripts\python.exe skill_runner.py "What is 12 x 9?"
```

```
ROUTED   NO_SKILL — answering directly
ANSWER   12 x 9 = 108
  we actually loaded .......... ~0 tokens (nothing)
  SAVED ....................... ~1,481 tokens
```

> **Both transcripts are graded.** A skill that always fires is not a skill, it
> is a system prompt with extra steps.

---

## The four moving parts

```
1. DISCOVERY   read every skills/*/SKILL.md, keep ONLY name + description
2. ROUTING     show the model that tiny menu — it picks one, or declines
3. LOADING     open the ONE matching SKILL.md in full
4. EXECUTION   run the skill's steps, with tools it can call
```

Step 3 is the whole trick.

Scale it in your head. At **100 skills**, the menu is ~8,000 tokens and you load
one body of ~400. Load all 100 and you are at ~40,000 tokens before the user has
said anything — and the relevant instruction is buried in 99 irrelevant ones.

**More context is not more intelligence.** That is `context rot`, and it is the
bridge into Module 6.

---

## Part 2 — build one together (30 min)

We'll write a fourth skill as a room. Follow along.

### Step 1 — the folder

```
skills/
└─ my-skill/
   ├─ SKILL.md          ← required. Everything else is optional.
   ├─ scripts/
   └─ resources/
```

### Step 2 — the frontmatter, which is the entire public API

```markdown
---
name: my-skill
description: <one line — and this line is doing all the work>
---
```

The router **only ever sees this line.** Not your instructions. Not your
scripts. Get this wrong and nothing else matters.

| ✗ weak | ✓ strong |
|---|---|
| `A skill for documents.` | `Turn a meeting transcript into dated action items. Use when the user asks for action items, follow-ups, or "who owns what" from a meeting.` |
| `Helps with code review.` | `Review a diff against our house style rules. Use when the user asks for a code review, PR feedback, or "does this follow our standards".` |

**The rule:** describe the **symptom the user will type**, not the feature you
built. Users don't say "I need document processing." They say "pull the action
items out of this."

Look at `file-organizer` from Part 1 — its trigger list is *"Your Downloads
folder is a chaotic mess."* That is a symptom, written in the user's voice.

### Step 3 — the body

Four sections. In this order.

```markdown
# Skill: <name>

## When to use this
Fires on: ...
Does NOT fire on: ...          ← people skip this. Don't.

## Steps
1. ...
2. Call `run_script("check.py", <draft>)`.
3. ...

## Rules
The non-negotiables. The things that must never happen.
```

The `Does NOT fire on` line is what keeps your skill dormant — and dormancy is
half your grade.

### Step 4 — push determinism into code

Anything **countable, checkable, or formattable** goes in a script.

Open `skills/jhf-brief/scripts/format_brief.py`. It enforces word count,
required headings, heading order, and a banned-phrase list. None of that is
reasoning. All of it is `len()` and `in`.

> **The rule, one more time:** a rule in a prompt is *advisory*. A gate in code
> is *enforced*.
>
> You watched this exact failure yesterday in the bridge project reviews — a
> student's prompt said "verify the headline," the model didn't, and it
> reported success anyway. Moving the check into code was the only thing that
> closed it.

### Step 5 — test both directions

```powershell
python skill_runner.py "<something that SHOULD match>"
python skill_runner.py "<something that should NOT>"
```

If it fires on both, your description is too broad. If it fires on neither,
you wrote it in your words instead of the user's.

---

## The tools a skill can call

| tool | what it does |
|---|---|
| `read_resource(path)` | read a file from **this** skill's folder — it cannot reach another skill's |
| `run_script(name, stdin)` | run a script from `scripts/`, get stdout back |
| `save_output(file, text)` | write the finished artifact to `output/` |
| `run_subagent(role, task)` | **start another agent** |

That last one is the closing section of the module.

---

## Part 3 — the closing idea: skills that run agents

```powershell
..\..\.venv\Scripts\python.exe skill_runner.py "Grade the submission in resources/sample-submission.md against the rubric"
```

Watch the trace:

```
  -> read_resource({'relative_path': 'resources/rubric.md'})
  -> read_resource({'relative_path': 'resources/sample-submission.md'})
  -> run_subagent(...)   x5
  -> save_output({'filename': 'grade-Sample_Student.md', ...})
```

**Five sub-agents.** One per rubric criterion. Each gets a fresh context window
and sees exactly one criterion.

### Why not just ask once for five scores?

Because it half-works, and it fails in a specific way. The model reads
criterion 1, forms an overall impression, and marks 2–5 to match. That is the
**halo effect** — and it's precisely why exam boards mark question-by-question
rather than script-by-script.

So `lab-grader` does what an exam board does:

```
lab-grader (a skill)
    │
    ├── sub-agent 1 ──► sees ONLY criterion 1 + the submission
    ├── sub-agent 2 ──► sees ONLY criterion 2 + the submission
    ├── ... x5
    │
    └── parent aggregates five verdicts into one report
```

Two things fall out of this, and both matter:

1. **No anchoring.** Examiner 4 cannot be swayed by a mark it never saw.
2. **The parent's context stays small.** It never sees the examiners' reasoning
   — only their verdicts. The submission could be 50 pages and the parent's
   context wouldn't grow.

### So what is a skill, really?

You started the day thinking: *a skill is a prompt in a folder.*

Here is where it lands:

| a skill can be… | example from today |
|---|---|
| a **procedure** | file-organizer — instructions, zero code |
| a **method** | canvas-design — think first, render second |
| a **toolchain** | artifacts-builder — scaffold script, bundle script |
| a **knowledge base** | ui-ux-pro-max — 192 rules, loaded five at a time |
| a **runtime** | open-slide — ships a whole React framework |
| an **orchestrator** | lab-grader — starts five agents and aggregates them |

> **The closing line:** we spent Module 5 teaching agents to *use* tools. A
> skill is the unit that says *how, in what order, and when to stop* — and when
> the job is big enough, it hires other agents to help.
>
> Tools give an agent hands. MCP gives it reach. **Skills give it a craft.**

---

## Troubleshooting

| symptom | fix |
|---|---|
| `404 ... 0 endpoints ... ZDR violation` | `$env:SKILL_MODEL="openai/gpt-4.1-mini"` — adding `tools` filters out endpoints, and an account guardrail can remove the last one |
| Hangs when no skill fires | you passed `tools=None`; omit the key instead of setting it null |
| `UnicodeDecodeError` from your script | `subprocess.run(..., encoding="utf-8")`, and reconfigure stdout inside the script |
| Skill fires on everything | your description describes the feature; describe the *symptom* |
| `MAX_STEPS` reached | your steps loop — add a stopping condition to the `Rules` section |
| Script not found | it must live in `scripts/`, and you call it by bare filename |
