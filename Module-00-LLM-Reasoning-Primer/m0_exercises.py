
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "openai/gpt-4o-mini"

# Exercise 1: Tokens
print("\n=== Exercise 1: Tokens ===")

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": "Explain what a token is in one sentence.",
        }
    ],
)

print("Answer:", r.choices[0].message.content)
print("Prompt tokens:", r.usage.prompt_tokens)
print("Completion tokens:", r.usage.completion_tokens)
print("Total tokens:", r.usage.total_tokens)


# Exercise 2: Statelessness
print("\n=== Exercise 2: Statelessness ===")

history = [
    {
        "role": "user",
        "content": "My favorite animal is a flamingo.",
    }
]

first = client.chat.completions.create(
    model=MODEL,
    messages=history,
)
print("First response:", first.choices[0].message.content)

second = client.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": "What is my favorite animal?",
        }
    ],
)
print("Without history:", second.choices[0].message.content)

history.append({
    "role": "assistant",
    "content": first.choices[0].message.content,
})
history.append({
    "role": "user",
    "content": "What is my favorite animal?",
})

third = client.chat.completions.create(
    model=MODEL,
    messages=history,
)
print("With history:", third.choices[0].message.content)


# Exercise 3: Temperature
print("\n=== Exercise 3: Temperature ===")

for temperature in [0, 0, 1.2, 1.2]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "Invent a name for a coffee shop.",
            }
        ],
        temperature=temperature,
    )

    print(
        f"Temperature {temperature}:",
        response.choices[0].message.content,
    )


# Exercise 4: Reasoning
print("\n=== Exercise 4: Reasoning ===")

question = (
    "A shop sells pens at 3 for $2. "
    "I have $10. How many pens can I buy, "
    "and how much change? Think step by step."
)

for model in ["openai/gpt-4o-mini", "openai/o4-mini"]:
    print(f"\nModel: {model}")
    start = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": question,
                }
            ],
            max_completion_tokens=1000,
        )

        elapsed = time.perf_counter() - start

        print("Answer:", response.choices[0].message.content)
        print("Total tokens:", response.usage.total_tokens)
        print("Time (seconds):", round(elapsed, 2))

    except Exception as e:
        print("Error:", str(e))
