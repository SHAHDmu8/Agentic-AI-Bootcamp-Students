# Memory Policy Note

## WRITE
I keep durable user preferences and meaningful facts, not every conversational line. In the lab implementation, `should_remember()` stores clauses such as `I prefer metric units` and `I'm researching renewable energy`, while deliberately refusing generic questions and answer fragments that do not represent stable user state. This keeps the long-term store useful and prevents junk from crowding the retrieval set.

## SUMMARISE
The short-term buffer uses a turn trigger: when the buffer grows past 6 turns, it folds the older messages into a rolling summary and keeps only the last 4 turns verbatim. That summary keeps durable facts and open questions while discarding repetition, which produces a sawtooth profile instead of an unbounded ramp. The live LLM path can trigger this fold, but the proper offline measurement must be taken by counting tokens in the text we actually send, not by assuming the summary itself is a win on a tiny sample.

## EVICT
I would not keep everything forever: stale or low-value memory should be removed by type and age, using TTL-style expiry for episodic entries and a decay policy for older facts that become less relevant. The privacy case is straightforward — if a preference or fact is no longer useful or was never meant to persist, it should be deleted rather than allowed to accumulate. This reduces long-term drift and reduces the risk of storing sensitive or outdated context.

## THE LEVER
The strongest measured lever in this exercise was `compress()`. Using the seeded exercise store, the baseline measured 10 memories with an estimate of 465 tokens and a billed count of 468. After `select()` the count fell to 3 memories and 248/251 tokens; after `compress()` the count fell to 2 memories and 214/217 tokens. That is a 54% prompt-size reduction versus the baseline (billed: 468 -> 217). The downside is that aggressive deduplication can remove relevant near-duplicates if the threshold is set too high, so the threshold must be tuned against the model's actual cosine behavior.
