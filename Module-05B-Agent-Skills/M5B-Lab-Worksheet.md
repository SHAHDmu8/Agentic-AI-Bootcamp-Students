<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 5B &middot; Lab Worksheet &mdash; Build &amp; Ship an Agent Skill</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
</div>

# M5B Lab — the run order

> **Goal:** read five real skills, build one of your own, and prove it fires on
> the right task, stays dormant on the wrong one, and costs almost nothing when
> idle.
>
> **Time:** ~2h 30m hands-on inside a 4h session.
> **You need:** your M5 environment + `OPENROUTER_API_KEY` in `.env`.

---

## Setup gate (5 min)

```powershell
.venv\Scripts\python.exe -m pip install -r Module-05B-Agent-Skills\requirements.txt
cd Module-05B-Agent-Skills\skill-runner
..\..\.venv\Scripts\python.exe skill_runner.py --list
```

✅ Three skills listed → you're ready.
❌ `ModuleNotFoundError` → wrong interpreter. Use the repo-root `.venv`.

If a later step returns `404 ... 0 endpoints ... ZDR violation`, your model
can't take tools on your account:

```powershell
$env:SKILL_MODEL="openai/gpt-4.1-mini"
```

---

## Part 1 — Five real skills (45 min) · `demos/`

Read `demos/README.md` alongside the live demos.

| # | Skill | Shape |
|:-:|---|---|
| 1 | file-organizer | 📄 instructions only |
| 2 | canvas-design | 🔁 a two-phase method |
| 3 | artifacts-builder | ⚙️ + executable scripts |
| 4 | ui-ux-pro-max | 📚 + a knowledge base |
| 5 | open-slide | 🧩 + its own runtime |

🧪 **Checkpoint.** Without looking: name the five shapes, and say which one you
think *your* scenario will need.

---

## Part 2 — Build one together (30 min)

Follow `skill-runner/README.md` § *Part 2*.

### Step 1 — scaffold

```
skill-runner/skills/my-skill/
├─ SKILL.md
├─ scripts/
└─ resources/
```

### Step 2 — frontmatter

```markdown
---
name: my-skill
description: <one line. The router sees ONLY this.>
---
```

🧪 **Checkpoint.** Read your description to the person next to you. If they
can't tell you *when* it should fire, rewrite it. Describe the **symptom the
user types**, not the feature you built.

### Step 3 — the body

```markdown
## When to use this
Fires on: ...
Does NOT fire on: ...

## Steps
1. ...

## Rules
...
```

🧪 **Checkpoint.** You have a `Does NOT fire on` line. (Most people skip this.
It's half the grade.)

### Step 4 — push determinism into code

Anything countable, checkable or formattable → a script.
Read `skills/jhf-brief/scripts/format_brief.py` for the pattern.

🧪 **Checkpoint.** Run your script standalone, outside the agent, on a tiny
input. It works before the model ever touches it.

### Step 5 — prove both directions

```powershell
python skill_runner.py "<should match>"      # fires, uses script/resource
python skill_runner.py "<should NOT match>"  # NO_SKILL, answers directly
```

🧪 **Checkpoint.** Both transcripts saved. Fires on both → description too
broad. Fires on neither → you wrote it in your words, not the user's.

---

## Part 3 — Progressive disclosure, measured (30 min)

```powershell
python skill_runner.py --list
python skill_runner.py "<your matching request>"
```

Copy the token report:

```
  skills on disk .............. 4
  menu shown to the router .... ~___ tokens
  if we had loaded ALL of them. ~___ tokens
  we actually loaded .......... ~___ tokens
  SAVED ....................... ~___ tokens
```

🧪 **Checkpoint.** You can explain what each line means, and what those numbers
become at 100 skills.

### Then: the skill that runs agents

```powershell
python skill_runner.py "Grade the submission in resources/sample-submission.md against the rubric"
```

Count the `run_subagent` calls in the trace. There should be five.

🧪 **Checkpoint.** You can say why five separate examiners beat one prompt
asking five questions. (The words you want are **halo effect**.)

---

## Part 4 — Your scenario (45 min) · `scenarios/`

Open **`scenarios/PICK-A-SCENARIO.html`** in a browser. Filter by shape or
difficulty, or hit **🎲 Surprise me**. Claim one. Copy the brief.

Full descriptions in `scenarios/SCENARIOS.md`.

**One scenario each.** Try not to duplicate someone else in the room.

You may look at existing skills first — `ComposioHQ/awesome-claude-skills` has
1000+. If one already exists for your scenario, read it, then write yours and
say in two sentences what you did differently. *Reading a good skill before
writing one is not cheating. It's how everyone learns this.*

🧪 **Checkpoint.** Your skill folder has `SKILL.md` **and** at least one script
or resource that actually gets called in the transcript.

---

## Showcase (20 min)

Two minutes each. Three things only:

1. **Read your description line out loud.** That's your entire public API.
2. **Fire it.** Once.
3. **The number.** What did disclosure save you?

No slides. Live terminal, or a recording.

---

## Deliverables

Open an issue using the project-submission template:

1. **Scenario number and title.**
2. **Your skill folder** — `SKILL.md` + ≥1 script or resource.
3. **Two transcripts** — fires · stays dormant.
4. **The token report.**
5. **Three sentences** — why a skill not a prompt · its narrow scope · what you
   pushed into code.

---

## Self-grade before you submit

You have the rubric *and* the grader. Use them.

```powershell
python skill_runner.py "Grade my submission at <path> against the rubric"
```

Rubric: `skill-runner/skills/lab-grader/resources/rubric.md`

| # | Criterion | You pass when |
|:-:|---|---|
| 1 | Discoverable | The description says **when** to use it, in the user's words |
| 2 | Narrow scope | It does **one** job |
| 3 | Disclosure is real | Full body loads only after a match — with the numbers to prove it |
| 4 | Fires *and* stays dormant | **Both** transcripts present |
| 5 | Determinism in code | A script or resource is genuinely called |

4 of 5 = PASS.

---

## Stretch (optional)

- **Add a second skill** and confirm the router picks the right one.
- **Give your skill a sub-agent** — one `run_subagent` call for a step that
  needs independent judgement.
- **Port it.** Drop your folder into Claude Code, Codex or Cursor. It's an open
  standard; it should just work. Report back if it doesn't.
- **Expose a skill's script as an MCP tool** (from M5) so other agents reuse it.

---

## Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `404 ... ZDR violation` | model can't take tools on this account | `$env:SKILL_MODEL="openai/gpt-4.1-mini"` |
| Hangs when no skill fires | `tools=None` → `"tools": null` | omit the key entirely |
| `â€"` in the terminal | Windows cp1252 console | reconfigure stdout to UTF-8 |
| `UnicodeDecodeError` from a script | subprocess pipe is cp1252 | `subprocess.run(..., encoding="utf-8")` |
| Skill always fires | description describes the **feature** | describe the **symptom** |
| Skill never fires | description uses your vocabulary | use the user's |
| `MAX_STEPS` reached | the steps loop | add a stopping condition under `Rules` |
| Script not found | wrong location | it must be in `scripts/`, called by bare filename |

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:30px;">
  <img src="../assets/jhf-logo.png" alt="JHF" height="26" style="vertical-align:middle; margin:0 12px;" />
  <img src="../assets/comcec-logo.png" alt="COMCEC" height="36" style="vertical-align:middle; margin:0 12px;" />
  <p style="color:#888; font-size:12px; margin-top:8px;">JHF Agentic AI Bootcamp &mdash; Module 5B Lab &middot; Organized by JHF &middot; in partnership with COMCEC</p>
</div>
