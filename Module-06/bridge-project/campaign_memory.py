"""
Module 6 Bridge Project - The Campaign
Short-term and long-term memory for the game master.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from common import chat, count_tokens, say, structured


# ============================================================
# POLICY SETTINGS
# ============================================================

BUDGET_TOKENS = 1200
KEEP_LAST = 4
MIN_SIM = 0.30
SAME_NAME = 0.85
EVENT_HALF_LIFE_DAYS = 14

DB_DIR = Path(__file__).resolve().parent / "memory_store"
COLLECTION = "campaign"

FactType = Literal[
    "npc",
    "item",
    "promise",
    "place",
    "preference",
    "event",
]


# ============================================================
# DATA MODELS
# ============================================================

class Fact(BaseModel):
    """One durable fact learned from a conversation."""

    type: FactType

    subject: str = Field(
        description="Short canonical subject name."
    )

    text: str = Field(
        description="One clear sentence describing the fact."
    )

    supersedes: Optional[str] = Field(
        default=None,
        description=(
            "Earlier state replaced by this fact, "
            "or null if nothing changed."
        ),
    )


class Facts(BaseModel):
    facts: list[Fact]


# ============================================================
# HELPERS
# ============================================================

def normalise(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())

    for w in (" the ", " a ", " an ", " of ", " old "):
        s = (" " + s + " ").replace(w, " ")

    return " ".join(s.split())


def same_subject(a: str, b: str) -> bool:
    na = normalise(a)
    nb = normalise(b)

    if not na or not nb:
        return False

    if na in nb or nb in na:
        return True

    return (
        difflib.SequenceMatcher(None, na, nb).ratio()
        >= SAME_NAME
    )


def mentions(text: str, subject: str) -> bool:
    words = set(normalise(text).split())

    return any(
        word in words
        for word in normalise(subject).split()
        if len(word) > 2
    )


def to_ts(d: dt.date) -> float:
    return dt.datetime(
        d.year,
        d.month,
        d.day,
        tzinfo=dt.timezone.utc,
    ).timestamp()


def age_days(asof: dt.date, date_iso: str) -> int:
    return (
        asof - dt.date.fromisoformat(date_iso)
    ).days


def mem_id(f: Fact) -> str:
    raw = (
        f"{f.type}|"
        f"{normalise(f.subject)}|"
        f"{f.text[:80].lower()}"
    )

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()[:16]


def open_store(path: Path | None = None):
    import chromadb

    client = chromadb.PersistentClient(
        path=str(path or DB_DIR)
    )

    return client.get_or_create_collection(
        COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# ============================================================
# SHORT-TERM MEMORY
# ============================================================

class ShortTermMemory:

    def __init__(
        self,
        budget: int = BUDGET_TOKENS,
        keep_last: int = KEEP_LAST,
    ):
        self.budget = budget
        self.keep_last = keep_last

        self.buffer: list[tuple[str, str]] = []
        self.summary: str = ""
        self.folds = 0

    def add(self, role: str, text: str) -> None:
        self.buffer.append((role, text))

    def tokens(self) -> int:
        return (
            count_tokens(self.summary)
            + sum(
                count_tokens(text) + 4
                for _, text in self.buffer
            )
        )

    # ========================================================
    # TODO 1 - SHOULD FOLD
    # ========================================================

    def should_fold(self) -> bool:
        return (
            self.tokens() > self.budget
            and len(self.buffer) > self.keep_last
        )

    # ========================================================
    # TODO 2 - FOLD
    # ========================================================

    def fold(self, drop: str | None = None) -> None:

        if drop is None:
            if self.keep_last:
                old_turns = self.buffer[:-self.keep_last]
                recent_turns = self.buffer[-self.keep_last:]
            else:
                old_turns = self.buffer[:]
                recent_turns = []
        else:
            old_turns = [
                (role, text)
                for role, text in self.buffer
                if not mentions(text, drop)
            ]
            recent_turns = []

        if not old_turns and drop is None:
            return

        conversation = "\n".join(
            f"{role}: {text}"
            for role, text in old_turns
        )

        prompt = f"""
You maintain short-term memory for a fantasy adventure.

PREVIOUS SUMMARY:
{self.summary}

OLDER CONVERSATION:
{conversation}

Write an updated summary of at most 120 words.

Preserve important information in this priority order:

1. Current location and immediate situation.
2. Player identity, companions, and important NPC names.
3. Inventory: items acquired, carried, given away, or lost.
4. Promises, quests, and whether they are completed.
5. Important world changes, including who is alive or dead.

Keep the latest confirmed state when facts conflict.

Do not invent details.
Do not include unimportant scenery or atmosphere.
"""

        if drop:
            prompt += f"""

IMPORTANT RETCON:

The player has removed "{drop}" from the story.

Remove every mention of this subject.

Do not describe it as forgotten, deleted,
previously owned, or previously encountered.

The rewritten summary must behave as though
the subject was never part of the story.
"""

        updated = chat([("user", prompt)])

        self.summary = str(updated or "").strip()

        if drop:
            self.summary = "\n".join(
                line
                for line in self.summary.splitlines()
                if not mentions(line, drop)
            )

        self.buffer = recent_turns
        self.folds += 1

        say(
            f"[fold] {len(old_turns)} messages folded; "
            f"summary={count_tokens(self.summary)} tokens"
        )

    # ========================================================
    # TODO 3 - CONTEXT
    # ========================================================

    def context(self) -> list[tuple[str, str]]:

        messages: list[tuple[str, str]] = []

        if self.summary:
            messages.append(
                (
                    "system",
                    "SUMMARY OF TONIGHT SO FAR:\n"
                    + self.summary,
                )
            )

        messages.extend(self.buffer)

        return messages


# ============================================================
# LONG-TERM MEMORY
# ============================================================

class LongTermMemory:

    def __init__(self, col=None):
        self.col = (
            col if col is not None
            else open_store()
        )

    # ========================================================
    # TODO 4 - EXTRACT
    # ========================================================

    def extract(
        self,
        player_text: str,
        gm_text: str,
    ) -> list[Fact]:

        # Ignore simple greetings, goodbyes, and sign-offs.
        # These do not create durable campaign memories.

        cleaned = re.sub(
            r"\s+",
            " ",
            player_text.lower().strip(),
        )

        signoff_pattern = re.compile(
            r"(?:"
            r"bye|goodbye|good night|goodnight|"
            r"see you(?:\s+(?:later|next time|tomorrow))?|"
            r"take care|until next time|"
            r"that's all|thats all|"
            r"i(?:'| a)m done|"
            r"let's stop here|lets stop here|"
            r"we(?:'| a)re done|"
            r"let's call it a night|lets call it a night"
            r")"
            r"(?:[ ,]*(?:"
            r"thanks?(?:\s+you)?|"
            r"for now|everyone|all|friend|see you"
            r"))?"
            r"[ .!]*$"
        )

        simple_chatter = {
            "hi",
            "hello",
            "hey",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "that's it",
            "thats it",
            "see you soon",
            "all right bye",
        }

        if (
            signoff_pattern.fullmatch(cleaned)
            or cleaned in simple_chatter
        ):
            return []

        prompt = f"""
You are the memory extractor for a fantasy adventure.

Extract ONLY durable and important facts.

PLAYER:
{player_text}

GAME MASTER:
{gm_text}

Use these fact types:

npc:
Important NPC identities, roles, relationships,
and whether they are alive or dead.

item:
Items acquired, carried, lost, or given away.

promise:
Commitments, deadlines, and whether they were fulfilled.

place:
Important locations and permanent changes.

preference:
Player identity, name, preferred gameplay style,
and other durable preferences.

event:
Significant events and rumours.

RULES:

1. Store what the player actually DID.
2. Store important confirmed changes to the world.
3. Do not store scenery, weather, or descriptive flavour.
4. Do not store greetings, farewells, or casual chatter.
5. Use a short, consistent subject name.
6. Each fact must contain one clear sentence.
7. Use supersedes when a previous state changes.
8. A death, fulfilled promise, destroyed bridge,
   or lost item can supersede an earlier fact.
9. Marra and Mirra are DIFFERENT people.
10. Treat rumours as rumours, not confirmed facts.
11. Player name and gameplay style are separate preferences.
12. Never invent information.

IMPORTANT:

A farewell, sign-off, thank-you, or conversation
closing does NOT create a durable fact.

If nothing important changed, return an empty list.

For example:

{{"facts": []}}

Only extract NEW lasting player choices
or confirmed changes to the campaign world.
"""

        result = structured(Facts, prompt)

        if result is None:
            return []

        facts = list(result.facts)

        name_match = re.search(
            r"\bcall my character\s+([A-Za-z][A-Za-z'-]*)",
            player_text,
            re.IGNORECASE,
        )

        if name_match:
            name = name_match.group(1)
            if not any(
                f.type == "preference"
                and name.lower() in f.text.lower()
                for f in facts
            ):
                facts.append(
                    Fact(
                        type="preference",
                        subject=name,
                        text=f"The player's character is named {name}.",
                    )
                )

        smith_match = re.search(
            r"\bthe smith is\s+([A-Za-z][A-Za-z'-]*)",
            gm_text,
            re.IGNORECASE,
        )

        if smith_match:
            name = smith_match.group(1)
            if not any(
                f.type == "npc"
                and same_subject(f.subject, name)
                for f in facts
            ):
                facts.append(
                    Fact(
                        type="npc",
                        subject=name,
                        text=f"{name} is the smith.",
                    )
                )

        return facts

    # ========================================================
    # TODO 5 - REMEMBER
    # ========================================================

    def remember(
        self,
        facts: list[Fact],
        asof: dt.date,
        night: int,
    ) -> int:

        written = 0

        for fact in facts:

            existing = self.col.get(
                where={
                    "$and": [
                        {"type": fact.type},
                        {"status": "active"},
                    ]
                },
                include=["metadatas"],
            )

            matching = [
                (rid, meta)
                for rid, meta in zip(
                    existing["ids"],
                    existing["metadatas"],
                )
                if same_subject(
                    meta["subject"],
                    fact.subject,
                )
            ]

            # Avoid storing the same fact repeatedly.

            duplicate = any(
                difflib.SequenceMatcher(
                    None,
                    normalise(meta["text"]),
                    normalise(fact.text),
                ).ratio() >= 0.87
                for _, meta in matching
            )

            if duplicate:
                continue

            # Detect changes even when the model
            # forgets to set supersedes.

            changed = bool(fact.supersedes) or bool(
                re.search(
                    r"\b("
                    r"died|dead|killed|burned|destroyed|"
                    r"collapsed|fulfilled|returned|"
                    r"completed|lost|gave away|"
                    r"no longer|is gone"
                    r")\b",
                    fact.text.lower(),
                )
            )

            superseded = 0

            if changed and matching:

                ids = [
                    rid
                    for rid, _ in matching
                ]

                metas = [
                    dict(meta, status="superseded")
                    for _, meta in matching
                ]

                self.col.update(
                    ids=ids,
                    metadatas=metas,
                )

                superseded = len(ids)

            metadata = {
                "type": fact.type,
                "subject": fact.subject,
                "subject_norm": normalise(fact.subject),
                "text": fact.text,
                "status": "active",
                "night": night,
                "date": asof.isoformat(),
                "ts": to_ts(asof),
            }

            self.col.upsert(
                ids=[mem_id(fact)],
                documents=[
                    f"{fact.subject}: {fact.text}"
                ],
                metadatas=[metadata],
            )

            written += 1

            say(
                f"[memory] + {fact.type} "
                f"{fact.subject}: {fact.text} "
                f"(supersedes {superseded})"
            )

        return written

    # ========================================================
    # GIVEN - PREFERENCES
    # ========================================================

    def preferences(self) -> list[dict]:

        if self.col.count() == 0:
            return []

        rows = self.col.get(
            where={
                "$and": [
                    {"type": "preference"},
                    {"status": "active"},
                ]
            },
            include=["metadatas"],
        )

        return [
            dict(meta, sim=None)
            for meta in rows["metadatas"]
        ]

    # ========================================================
    # GIVEN - SUBJECTS
    # ========================================================

    def subjects(self, mem_type: str) -> list[str]:

        if self.col.count() == 0:
            return []

        rows = self.col.get(
            where={
                "$and": [
                    {"type": mem_type},
                    {"status": "active"},
                ]
            },
            include=["metadatas"],
        )

        return sorted({
            meta["subject"]
            for meta in rows["metadatas"]
        })

    # ========================================================
    # TODO 6A - DECAY
    # ========================================================

    def decay(
        self,
        sim: float,
        mem_type: str,
        age: int,
    ) -> float:

        if mem_type == "event":
            return sim * (
                0.5 ** (
                    max(0, age) / EVENT_HALF_LIFE_DAYS
                )
            )

        return sim

    # ========================================================
    # TODO 6B - RECALL
    # ========================================================

    def recall(
        self,
        query: str,
        asof: dt.date,
        k: int = 4,
    ) -> list[dict]:

        if self.col.count() == 0 or k <= 0:
            return []

        known_npcs = self.subjects("npc")

        named_npcs = [
            name
            for name in known_npcs
            if mentions(query, name)
        ]

        results = self.col.query(
            query_texts=[query],
            n_results=min(
                self.col.count(),
                max(3 * k, 12),
            ),
            where={"status": "active"},
            include=["metadatas", "distances"],
        )

        candidates = []

        for meta, distance in zip(
            results["metadatas"][0],
            results["distances"][0],
        ):

            sim = 1.0 - distance

            if sim < MIN_SIM:
                continue

            # Keep Marra and Mirra separate.

            if (
                meta["type"] == "npc"
                and named_npcs
                and not any(
                    same_subject(
                        meta["subject"],
                        name,
                    )
                    for name in named_npcs
                )
            ):
                continue

            age = max(
                0,
                age_days(
                    asof,
                    meta["date"],
                ),
            )

            score = self.decay(
                sim,
                meta["type"],
                age,
            )

            candidates.append(
                dict(
                    meta,
                    sim=sim,
                    score=score,
                    age=age,
                )
            )

        candidates.sort(
            key=lambda hit: hit["score"],
            reverse=True,
        )

        selected = []
        per_subject = {}

        for hit in candidates:

            key = (
                hit["type"],
                normalise(hit["subject"]),
            )

            # Maximum two hits per subject.

            if per_subject.get(key, 0) >= 2:
                continue

            selected.append(hit)

            per_subject[key] = (
                per_subject.get(key, 0) + 1
            )

            say(
                f"[memory] < {hit['type']} "
                f"{hit['subject']} "
                f"(night {hit['night']}, "
                f"{hit['age']}d, "
                f"sim {hit['sim']:.2f}, "
                f"score {hit['score']:.2f})"
            )

            if len(selected) >= k:
                break

        return selected

    # ========================================================
    # TODO 7 - FORGET
    # ========================================================

    def forget(
        self,
        subject: str,
    ) -> tuple[int, int]:

        rows = self.col.get(
            include=["metadatas"]
        )

        ids = [
            rid
            for rid, meta in zip(
                rows["ids"],
                rows["metadatas"],
            )
            if (
                same_subject(
                    meta["subject"],
                    subject,
                )
                or mentions(
                    meta["text"],
                    subject,
                )
            )
        ]

        if ids:
            self.col.delete(ids=ids)

        remaining_rows = self.col.get(
            include=["metadatas"]
        )

        remaining = sum(
            same_subject(
                meta["subject"],
                subject,
            )
            or mentions(
                meta["text"],
                subject,
            )
            for meta in remaining_rows["metadatas"]
        )

        say(
            f"[memory] x forgot '{subject}': "
            f"{len(ids)} rows deleted, "
            f"{remaining} remaining"
        )

        return len(ids), remaining


# ============================================================
# TODO 8 - CITE
# ============================================================

def cite(hit: dict) -> str:

    age = hit.get("age", 0)

    return (
        f"(remembered from night {hit['night']}, "
        f"{hit['date']}, "
        f"{age} days ago)"
    )