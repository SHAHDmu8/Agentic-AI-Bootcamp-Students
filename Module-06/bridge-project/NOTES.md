# Module 6 Bridge Project — The Campaign

## Memory implementation
Implemented short-term memory folding, long-term fact extraction and persistence, retrieval with event decay, superseding facts, targeted forgetting, and citations.

## Verification
All 17 checks passed in verify_memory.py.

## Short-term memory and token budget
- Configured short-term memory budget: 1,200 tokens.
- KEEP_LAST: 4 turns.
- Each memory-enabled night triggered 2 folds.
- Maximum full prompt: Night 1 = 2,308; Night 2 = 2,314; Night 3 = 2,284 tokens.
- The full prompt includes system instructions and retrieved memories, so it can exceed the short-term memory budget.

## First missed continuity question
Night 2: "What tone did I ask you to keep for this game? Quote me."
Expected: "keep it light — no gore, this is a cosy game."
The model answered with a different description of a gentle tone rather than the original wording.

## Memory vs. Goldfish
| Night | Memory quiz | Goldfish quiz |
|---|---:|---:|
| 2 | 7/10 | 3/10 |
| 3 | 8/10 | 4/10 |

## Marra / Mirra identity check
Night 3 correctly answered:
- Marra the smith is dead.
- Mirra the herbalist is alive.

The names refer to different NPCs. Long-term memory successfully preserved this distinction.

## Retcon experiment
Night 3 retcon: forget the amulet.
- 6 matching memory rows deleted.
- 0 matching rows remaining.
- Short-term summary mentioned the amulet after re-fold: no.
- GM's next answer mentioned the amulet: no.

The retcon passed all three checks.

## Limitations observed
The memory-enabled GM sometimes contradicted established facts. For example, early in Night 3 it described the bridge as still standing even though it had burned in Night 2. The quiz also missed the original tone instruction. Persistent memory improves continuity but does not guarantee perfect recall.
