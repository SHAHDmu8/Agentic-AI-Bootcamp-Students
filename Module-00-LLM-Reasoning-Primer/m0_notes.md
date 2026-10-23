# Module 0 — LLM Reasoning Primer

## Exercise 1: Tokens and API Usage

**Model:** `openai/gpt-4o-mini`

**Prompt:** Explain what a token is in one sentence.

**Observed results:**
- Prompt tokens: 16
- Completion tokens: 31
- Total tokens: 47

**Observation:** The API returned a response and reported token usage. The model interpreted "token" in a general digital/blockchain context rather than specifically as an LLM text-processing unit.

## Exercise 2: Statelessness

**Model:** `openai/gpt-4o-mini`

**First request:** My favorite animal is a flamingo.

**Second request:** What is my favorite animal?

**Without conversation history:** The model could not identify my favorite animal.

**With conversation history:** The model correctly answered that my favorite animal is a flamingo.

**Observation:** Each API request is independent unless previous conversation messages are explicitly included.

## Exercise 3: Temperature

**Model:** `openai/gpt-4o-mini`

**Prompt:** Invent a name for a coffee shop.

| Temperature | Response |
|---|---|
| 0 | Bean There, Brewed That |
| 0 | Bean There, Brewed That |
| 1.2 | Perk & Pour Café |
| 1.2 | Java Junction |

**Observation:** Temperature 0 produced identical responses in this test, while temperature 1.2 produced different creative names.

## Exercise 4: Reasoning Models

**Problem:** A shop sells pens at 3 for $2. I have $10. How many pens can I buy, and how much change?

| Metric | GPT-4o-mini | o4-mini |
|---|---|---|
| Answer | 15 pens, $0 change | 15 pens, $0 change |
| Total tokens | 407 | 613 |
| Latency | 8.37 seconds | 5.93 seconds |

**Observation:** Both models answered correctly. The reasoning model used more tokens but was faster in this particular run. A single measurement is not enough to establish a general speed advantage.

## Reflection

**1. What is an LLM?**

A Large Language Model is an AI model trained on large amounts of text to understand and generate language by predicting tokens.

**2. Why are API calls stateless?**

Each API call is independent, so the application must provide previous messages when conversation context is needed.

**3. Why use temperature = 0 for agents?**

A low temperature makes outputs more consistent and predictable, which is useful for reliable agent workflows.

**4. When is a reasoning model worth the extra cost?**

A reasoning model is useful for complex, multi-step tasks where stronger reasoning can justify additional token usage and cost.