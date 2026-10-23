"""
Module 6 Lab — STARTER
Personal Knowledge Assistant: short-term (summarized) + long-term (persistent vector) memory.

Part 1: conversation buffer + summarization.
Part 2: vector write/read paths, persistence across restart, citations.

Fill in the TODOs. Each TODO names the worksheet step it belongs to.

Install (into the SAME venv as Modules 1-5, Python 3.12):
    Module-02\\.venv\\Scripts\\python.exe -m pip install -r Module-06\\requirements.txt
Check:
    Module-02\\.venv\\Scripts\\python.exe Module-06\\m6_preflight.py
Run (two SEPARATE processes — that is the whole point of Part 2):
    python memory_agent.py --run1
    python memory_agent.py --run2

Your key lives in the repo-root .env (OPENROUTER_API_KEY=sk-or-...), same as M1-M5.
"""

import argparse
import datetime
import hashlib
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency for tests
    ChatOpenAI = None

try:
    import chromadb
except Exception:  # pragma: no cover - optional dependency for tests
    chromadb = None

# Windows consoles default to cp1252 and turn every em-dash into mojibake.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")      # repo-root .env

SUMMARIZE_AFTER_TURNS = 6
KEEP_LAST = 4
TOP_K = 3
DB_DIR = HERE / "memory_store"   # MUST persist to disk for cross-restart recall.
                                 # Next to THIS FILE, not the current directory — a cwd-relative
                                 # path is the #1 cause of "it forgot everything after restart".


def configure_llm():
    if ChatOpenAI is None:
        return None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(
        model=os.getenv("MODEL", "openai/gpt-4o-mini"), temperature=0,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=api_key,
    )


# real LLM is only used when OpenRouter is configured from the repo-root .env.
llm = configure_llm()


# ---------------------------------------------------------------------------
# SHORT-TERM MEMORY
# ---------------------------------------------------------------------------
class ShortTermMemory:
    def __init__(self):
        self.buffer = []      # recent turns, verbatim
        self.summary = ""     # rolling summary of older turns
        self.summary_source = "none"

    def add(self, role: str, text: str):
        self.buffer.append({"role": role, "text": text})

        if len(self.buffer) > SUMMARIZE_AFTER_TURNS:
            older = self.buffer[:-KEEP_LAST]
            older_text = "\n".join(f"{entry['role']}: {entry['text']}" for entry in older)
            if llm is not None:
                summary_prompt = (
                    "Update the running summary of this conversation. "
                    "Keep durable facts and open questions; discard repetition. "
                    "Max 80 words.\n\n" + older_text
                )
                try:
                    resp = llm.invoke(summary_prompt)
                    summary = (getattr(resp, "content", str(resp)) or "").strip()
                    self.summary_source = "llm"
                except Exception:
                    summary = f"[fallback summary] {older_text.strip()}"
                    self.summary_source = "fallback"
            else:
                summary = f"[fallback summary] {older_text.strip()}"
                self.summary_source = "fallback"

            if not summary:
                summary = f"[fallback summary] {older_text.strip()}"
                self.summary_source = "fallback"

            self.summary = summary
            self.buffer = self.buffer[-KEEP_LAST:]
            print(f"[trigger fired] summarized {len(older)} older turns; buffer kept {len(self.buffer)}")
            print(f"[summary updated:{self.summary_source}] {self.summary}")

    def context(self) -> str:
        summary_text = self.summary.strip() if self.summary else "none"
        recent = "\n".join(f"{entry['role']}: {entry['text']}" for entry in self.buffer)
        if recent:
            return f"SUMMARY: {summary_text}\nRECENT:\n{recent}"
        return f"SUMMARY: {summary_text}\nRECENT: none"


# ---------------------------------------------------------------------------
# LONG-TERM MEMORY (persistent vector store)
# ---------------------------------------------------------------------------
def split_memories(text: str) -> list[str]:
    if not text:
        return []
    normalized = re.sub(r"\s*;\s*", " ; ", text.strip(), flags=re.IGNORECASE)
    normalized = re.sub(r"\s+and\s+(?=I\b)", " ; ", normalized, flags=re.IGNORECASE)
    parts = [part.strip(" .,;") for part in normalized.split(";")]
    return [part for part in parts if part]


def should_remember(text: str):
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    if re.search(r"\bI\s+(?:prefer|like|want|need|enjoy|favor)\b", cleaned, flags=re.IGNORECASE):
        return "preference"
    if re.search(r"\bI(?:'m| am)\s+researching\b|\bmy project\b|\bmy work\b|\bmy goal\b", cleaned, flags=re.IGNORECASE):
        return "fact"
    if re.search(r"\bI\s+(?:have|am|live|work|study)\b", cleaned, flags=re.IGNORECASE):
        return "fact"
    return None


def write_memory(text: str, mem_type: str = "fact"):
    if collection is None:
        return None
    normalized = text.strip()
    if not normalized:
        return None
    today = datetime.date.today().isoformat()
    ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    mem_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    metadata = {
        "text": normalized,
        "source": "user",
        "timestamp": today,
        "type": mem_type,
        "ts": ts,
    }
    collection.upsert(ids=[mem_id], documents=[normalized], metadatas=[metadata])
    print(f"[stored {mem_type}] {normalized}")
    return metadata


def recall(query: str, k: int = TOP_K) -> list:
    if collection is None:
        return []
    result = collection.query(query_texts=[query], n_results=k, include=["documents", "metadatas", "distances"])
    memories = []
    for doc, meta, dist in zip(result.get("documents", [[]])[0], result.get("metadatas", [[]])[0], result.get("distances", [[]])[0]):
        if dist is None:
            distance = 0.0
        else:
            distance = float(dist)
        similarity = max(0.0, 1.0 - distance)
        if similarity < 0.2:
            continue
        metadata = dict(meta or {})
        memories.append({
            "text": doc,
            "type": metadata.get("type", "fact"),
            "timestamp": metadata.get("timestamp", datetime.date.today().isoformat()),
            "similarity": round(similarity, 4),
            "source": metadata.get("source", "user"),
        })
    return memories


# ---------------------------------------------------------------------------
# AGENT TURN
# ---------------------------------------------------------------------------
def answer(user_text: str, stm: ShortTermMemory) -> str:
    for piece in split_memories(user_text):
        mem_type = should_remember(piece)
        if mem_type:
            write_memory(piece, mem_type)

    recalled = recall(user_text, k=TOP_K)

    rules = (
        "You are a helpful personal assistant. "
        "Treat every preference in RECALLED MEMORIES as an instruction. "
        "Cite each memory you apply with the exact format '(from your stored <type>, <YYYY-MM-DD>)'. "
        "Be concise and factual."
    )

    memory_block = ""
    if recalled:
        for idx, memory in enumerate(recalled, 1):
            memory_block += f"{idx}. {memory['text']} (type={memory['type']}, date={memory['timestamp']})\n"
        memory_block = "RECALLED MEMORIES:\n" + memory_block.strip()
    else:
        memory_block = "RECALLED MEMORIES:\nNone"

    prompt_messages = [
        {"role": "system", "content": rules},
        {"role": "system", "content": memory_block},
        {"role": "system", "content": f"SUMMARY:\n{stm.summary.strip() if stm.summary else 'none'}"},
    ]

    for entry in stm.buffer:
        prompt_messages.append({"role": entry["role"], "content": entry["text"]})
    prompt_messages.append({"role": "user", "content": user_text})

    response_text = ""
    prompt_size = 0
    if llm is None:
        response_text = "I can answer this once the OpenRouter LLM is available."
    else:
        llm_response = llm.invoke(prompt_messages)
        response_text = getattr(llm_response, "content", str(llm_response)) or "I don't have a response yet."
        usage = (getattr(llm_response, "usage_metadata", {}) or {})
        prompt_size = usage.get("input_tokens", 0)

    print(f"[receipt] prompt size {prompt_size} | recalled: {len(recalled)}")
    if recalled:
        print("[recalled memories]")
        for memory in recalled:
            print(f"  - {memory['text']} | type={memory['type']} | date={memory['timestamp']} | sim={memory['similarity']}")

    stm.add("user", user_text)
    stm.add("assistant", response_text)
    return response_text


# ---------------------------------------------------------------------------
# CLI — do not change; the worksheet's commands depend on these flags
# ---------------------------------------------------------------------------
RUN1 = "I prefer metric units and I'm researching renewable energy."
RUN2 = "Give me a quick figure for solar capacity."

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run1", action="store_true", help=f'send "{RUN1}"')
    ap.add_argument("--run2", action="store_true", help=f'send "{RUN2}" — in a NEW process')
    ap.add_argument("--chat", action="store_true", help="interactive; type quit to leave")
    args = ap.parse_args()

    stm = ShortTermMemory()
    print(f"[store: {DB_DIR}  pid: {os.getpid()}]")

    if args.run1:
        print(answer(RUN1, stm))
    elif args.run2:
        print(answer(RUN2, stm))
    elif args.chat:
        while (user := input("\nyou > ").strip().lower()) not in {"quit", "exit", "q"}:
            if user:
                print("\nassistant > " + answer(user, stm))
    else:
        ap.print_help()
