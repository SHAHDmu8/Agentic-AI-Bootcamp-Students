"""
skill_runner.py — a working Agent Skills runtime, in about 300 lines.

WHY THIS FILE EXISTS
--------------------
Claude Code, Copilot CLI and claude.ai can all load skills. None of them show
you *how*. This file is the same idea with the lid off, so you can watch every
moving part:

    1. DISCOVERY      read every skills/*/SKILL.md, keep only name + description
    2. ROUTING        show the model that tiny menu, let it pick (or decline)
    3. LOADING        open the ONE matching SKILL.md in full
    4. EXECUTION      run the skill's steps, with tools it can call

Step 3 is the whole trick. It is called PROGRESSIVE DISCLOSURE, and this file
prints the receipts for it every run, so you can see the saving instead of
taking my word for it.

RUN IT
------
    python skill_runner.py --list
    python skill_runner.py "Give me a one-page brief on agentic RAG"
    python skill_runner.py "What is 12 x 9?"            # no skill should fire
    python skill_runner.py --no-skills "...same prompt..."   # the control group

Needs OPENROUTER_API_KEY in the repo-root .env — the same one from Module 5.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Windows consoles default to cp1252 and turn every em-dash into mojibake.
# One line here saves twenty minutes of "why is my output broken" in the lab.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).parent
SKILLS_DIR = HERE / "skills"
OUTPUT_DIR = HERE / "output"

load_dotenv(HERE.parent.parent / ".env")
load_dotenv(HERE.parent / ".env")
load_dotenv(HERE / ".env")

MODEL = os.getenv("SKILL_MODEL", "openai/gpt-4.1-mini")
ROUTER_MAX_TOKENS = int(os.getenv("SKILL_ROUTER_MAX_TOKENS", "512"))
MAIN_RESPONSE_MAX_TOKENS = int(os.getenv("SKILL_RESPONSE_MAX_TOKENS", "2048"))
SUBAGENT_MAX_TOKENS = int(os.getenv("SKILL_SUBAGENT_MAX_TOKENS", "1024"))
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)

MAX_STEPS = 8

# Not every model on OpenRouter can be given tools, and some accounts add a
# zero-data-retention guardrail that quietly removes the last eligible endpoint.
# When that happens the API returns a 404 that says nothing useful, so we
# translate it here.
TOOL_HELP = """
Your model cannot be given tools on this account.

OpenRouter filters endpoints in stages. Adding `tools` removes every endpoint
that does not support tool calling; an account guardrail (e.g. zero data
retention) can then remove what is left. The result is a 404 that looks like
the model does not exist.

Pick a model that survives both filters:

    setx SKILL_MODEL openai/gpt-4.1-mini          (Windows, new shell after)
    $env:SKILL_MODEL="openai/gpt-4.1-mini"        (this shell only)

Known good at the time of writing: openai/gpt-4.1-mini, openai/gpt-4o,
meta-llama/llama-3.3-70b-instruct.
"""


def est_tokens(text: str) -> int:
    """Rough token estimate. ~4 characters per token is close enough to make
    the progressive-disclosure saving visible, and costs us no dependency."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# 1. DISCOVERY — the cheap part
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str

    @property
    def menu_line(self) -> str:
        return f"- {self.name}: {self.description}"


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a SKILL.md into its YAML-ish frontmatter and its body.

    We hand-roll this instead of importing PyYAML for two reasons: it keeps the
    dependency list at zero-new, and it forces you to see that the format is
    not magic. It is a `---` fence with `key: value` lines.
    """
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    head, body = raw[3:end], raw[end + 4 :]
    meta: dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body.lstrip("\n")


def discover_skills(root: Path = SKILLS_DIR) -> list[Skill]:
    """Read every skill on disk. Note what we KEEP versus what we READ:
    the menu the model sees is built from name + description only."""
    found: list[Skill] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        raw = skill_md.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        found.append(
            Skill(
                name=meta.get("name", skill_md.parent.name),
                description=meta.get("description", "(no description)"),
                path=skill_md.parent,
                body=body,
            )
        )
    return found


# ---------------------------------------------------------------------------
# 2. TOOLS — what a skill is allowed to do once it is loaded
# ---------------------------------------------------------------------------

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "read_resource",
            "description": "Read a file from the active skill's folder (e.g. 'resources/brief-template.md').",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_script",
            "description": "Run a Python script from the active skill's scripts/ folder, passing text on stdin. Returns stdout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_name": {"type": "string"},
                    "stdin_text": {"type": "string"},
                },
                "required": ["script_name", "stdin_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_output",
            "description": "Save the finished artifact to the output/ folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_subagent",
            "description": (
                "Delegate a self-contained job to a SECOND agent with its own fresh context. "
                "Use when a step needs independent judgement, e.g. grading or reviewing. "
                "Returns only that agent's final answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "System prompt for the sub-agent."},
                    "task": {"type": "string", "description": "The job, with all context it needs."},
                },
                "required": ["role", "task"],
            },
        },
    },
]


class Toolbox:
    """Tools are bound to the ACTIVE skill's folder, so one skill can never
    read another skill's resources. Small detail, real isolation."""

    def __init__(self, skill: Skill | None, trace: list):
        self.skill = skill
        self.trace = trace

    def read_resource(self, relative_path: str) -> str:
        if not self.skill:
            return "ERROR: no skill is active."
        target = (self.skill.path / relative_path).resolve()
        if not str(target).startswith(str(self.skill.path.resolve())):
            return "ERROR: path escapes the skill folder."
        if not target.exists():
            return f"ERROR: {relative_path} not found."
        return target.read_text(encoding="utf-8")

    def run_script(self, script_name: str, stdin_text: str) -> str:
        if not self.skill:
            return "ERROR: no skill is active."
        script = (self.skill.path / "scripts" / Path(script_name).name).resolve()
        if not script.exists():
            return f"ERROR: scripts/{script_name} not found."
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.stdout if proc.returncode == 0 else f"ERROR: {proc.stderr}"

    def save_output(self, filename: str, content: str) -> str:
        OUTPUT_DIR.mkdir(exist_ok=True)
        target = OUTPUT_DIR / Path(filename).name
        target.write_text(content, encoding="utf-8")
        return f"Saved {target.name} ({len(content)} chars) to output/"

    def run_subagent(self, role: str, task: str) -> str:
        """THE POINT OF THE CLOSING SECTION.

        A skill is not only instructions. A skill can start another agent.
        That sub-agent gets its own clean context window, does one job, and
        returns one answer. The parent never sees the sub-agent's scratch work
        — which is exactly why its context stays small."""
        reply = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_tokens=SUBAGENT_MAX_TOKENS,
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": task},
            ],
        )
        return reply.choices[0].message.content or ""

    def dispatch(self, name: str, args: dict) -> str:
        fn = getattr(self, name, None)
        if fn is None:
            return f"ERROR: unknown tool {name}"
        try:
            return fn(**args)
        except Exception as exc:  # surfaced to the model so it can recover
            return f"ERROR: {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# 3. ROUTING + EXECUTION
# ---------------------------------------------------------------------------

ROUTER_PROMPT = """You are a router. You are shown a menu of available skills.

{menu}

Decide whether ONE of these skills is the right playbook for the user's request.

Reply with EXACTLY one line and nothing else:
  USE_SKILL: <name>     if a skill clearly matches
  NO_SKILL              if none of them match

Do not answer the user's question. Route only."""


def route(skills: list[Skill], user_request: str) -> tuple[str | None, str]:
    menu = "\n".join(s.menu_line for s in skills)
    system = ROUTER_PROMPT.format(menu=menu)
    reply = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=ROUTER_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_request},
        ],
    ).choices[0].message.content or ""
    reply = reply.strip()
    if reply.upper().startswith("USE_SKILL:"):
        picked = reply.split(":", 1)[1].strip()
        for s in skills:
            if s.name.lower() == picked.lower():
                return s.name, system
    return None, system


def run(user_request: str, use_skills: bool = True, verbose: bool = True) -> str:
    skills = discover_skills() if use_skills else []
    trace: list = []

    chosen: Skill | None = None
    router_system = ""
    if skills:
        picked_name, router_system = route(skills, user_request)
        chosen = next((s for s in skills if s.name == picked_name), None)

    if verbose:
        print("=" * 68)
        print(f"REQUEST  {user_request}")
        print(f"SKILLS   {len(skills)} on disk: {', '.join(s.name for s in skills) or '(none)'}")
        print(f"ROUTED   {chosen.name if chosen else 'NO_SKILL — answering directly'}")
        print("=" * 68)

    system = "You are a helpful assistant."
    if chosen:
        system = (
            "You are a helpful assistant. A skill has been loaded for this request. "
            "Follow its instructions exactly.\n\n"
            f"=== SKILL: {chosen.name} ===\n{chosen.body}\n=== END SKILL ==="
        )

    box = Toolbox(chosen, trace)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_request},
    ]

    final = ""
    for _ in range(MAX_STEPS):
        # Build kwargs conditionally. Passing `tools=None` is NOT the same as
        # omitting it — the SDK serialises it as "tools": null, which some
        # OpenRouter providers stall on. Omit the key entirely instead.
        kwargs = {"model": MODEL, "temperature": 0, "messages": messages, "max_tokens": MAIN_RESPONSE_MAX_TOKENS}
        if chosen:
            kwargs["tools"] = TOOL_SPECS
        try:
            resp = client.chat.completions.create(**kwargs).choices[0].message
        except Exception as exc:
            if "endpoints" in str(exc).lower() or "tool" in str(exc).lower():
                print(f"\nModel `{MODEL}` failed on a tool call.\n{TOOL_HELP}")
                raise SystemExit(1)
            raise

        if not resp.tool_calls:
            final = resp.content or ""
            break

        messages.append(resp.model_dump(exclude_none=True))
        for call in resp.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = box.dispatch(call.function.name, args)
            trace.append((call.function.name, str(args)[:70]))
            if verbose:
                print(f"  -> {call.function.name}({str(args)[:60]}...)")
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result[:6000]}
            )
    else:
        final = "Stopped: hit MAX_STEPS."

    if verbose:
        report(skills, chosen, router_system, trace, final)
    return final


def report(skills, chosen, router_system, trace, final) -> None:
    """The receipts. This is the part students screenshot."""
    menu_cost = est_tokens(router_system)
    all_bodies = sum(est_tokens(s.body) for s in skills)
    loaded = est_tokens(chosen.body) if chosen else 0
    saved = all_bodies - loaded

    print("\n" + "-" * 68)
    print("ANSWER\n")
    print(final.strip()[:1500])
    print("\n" + "-" * 68)
    print("PROGRESSIVE DISCLOSURE — what it actually cost")
    print(f"  skills on disk .............. {len(skills)}")
    print(f"  menu shown to the router .... ~{menu_cost:,} tokens")
    print(f"  if we had loaded ALL of them. ~{all_bodies:,} tokens")
    print(f"  we actually loaded .......... ~{loaded:,} tokens"
          f" ({chosen.name if chosen else 'nothing'})")
    print(f"  SAVED ....................... ~{saved:,} tokens")
    if trace:
        print("\n  trace:")
        for name, detail in trace:
            print(f"    {name:<14} {detail}")
    print("-" * 68)


def main() -> None:
    ap = argparse.ArgumentParser(description="A minimal Agent Skills runtime.")
    ap.add_argument("request", nargs="*", help="what you want")
    ap.add_argument("--list", action="store_true", help="show the skill menu and exit")
    ap.add_argument("--no-skills", action="store_true", help="control group: disable skills")
    args = ap.parse_args()

    if args.list:
        skills = discover_skills()
        print(f"\n{len(skills)} skill(s) discovered in {SKILLS_DIR}\n")
        for s in skills:
            print(f"  {s.name}")
            print(f"    {s.description}")
            print(f"    full body: ~{est_tokens(s.body):,} tokens, "
                  f"loaded only on match\n")
        return

    if not args.request:
        ap.error("give me a request, or use --list")

    run(" ".join(args.request), use_skills=not args.no_skills)


if __name__ == "__main__":
    main()
