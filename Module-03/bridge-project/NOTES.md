# Module 3 Bridge Project — Reflection Notes

## a. Where did the budget force a real trade-off?

The final run used **7 out of 9 available GLEIF lookups**, allowing all seven suppliers to receive a registry lookup. Therefore, the final run did not require skipping a supplier.

However, the earlier implementation incorrectly counted web searches against the GLEIF lookup budget. That version exhausted its nine counted searches after assessing six suppliers and left Maersk A/S unchecked. This revealed an important planning problem: combining different types of searches under one budget can cause an agent to skip important checks unnecessarily.

I corrected the budget accounting so only GLEIF registry lookups count toward `MAX_LOOKUPS = 9`. Web searches and mandatory sanctions screening do not consume that budget.

The final run assessed all seven suppliers, including Maersk A/S, which received a CONDITIONS verdict. Two GLEIF lookups remained unused.

## b. What sanctions threshold did you set, and why that number?

I used a sanctions similarity threshold of **0.90**.

The sanctions screening identified Al Wasel and Babel General Trading LLC with a score of **1.00** under the IRAQ2 programme. A lower threshold, such as 0.80, could incorrectly flag legitimate suppliers because of similarities in common company names. For example, Almarai Company produced a similarity score of approximately **0.81** in the earlier screening results.

A threshold that is too low increases false positives and can unnecessarily delay legitimate payments. A threshold that is too high increases the risk of missing a genuinely sanctioned entity.

Importantly, a similarity score is a screening signal, not definitive proof of identity. Potential sanctions matches require appropriate verification and escalation.

## c. Where did your agent nearly get it wrong?

The first major issue was **budget accounting**. The original implementation charged both web searches and GLEIF lookups against the same nine-lookup limit. As a result, the agent stopped after six suppliers and left Maersk A/S unassessed.

I corrected the implementation so that the nine-lookup limit applies only to GLEIF registry searches. I also changed the graph routing so the agent continues processing suppliers even if the GLEIF budget is exhausted, allowing mandatory sanctions screening to continue.

Another important risk was **legal-entity ambiguity**. Siemens AG produced multiple similar GLEIF candidates, so the agent returned CONDITIONS instead of approving the first available result.

The project also required distinguishing between a missing LEI record and an unavailable lookup, and between a company's entity status and its LEI registration status.

The earlier implementation was run twice and produced stable verdicts. After the budget correction, the final observed run returned seven verdicts using seven GLEIF lookups. A second run of the corrected version is still needed to confirm stability after this change.