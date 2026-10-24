from __future__ import annotations

import os
import sys

from dotenv import find_dotenv, load_dotenv
from crewai import Agent, Crew, LLM, Process, Task

load_dotenv()
load_dotenv(find_dotenv(usecwd=True))

llm = None


def get_llm() -> LLM:
    """Create the shared OpenRouter-backed CrewAI language model."""
    global llm
    if llm is not None:
        return llm

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found. Add it to the repo root .env file before running this script."
        )

    llm = LLM(
        model="openrouter/dots-studio/dots-3-note-preview:free",
        temperature=0,
        api_key=api_key,
    )
    return llm


def build_crew(topic: str) -> Crew:
    teacher = Agent(
        role="Patient Study Guide Teacher",
        goal="Produce accurate, beginner-friendly study material that explains concepts clearly without inventing details.",
        backstory=(
            "You are a careful educational assistant who explains technical topics in plain language. "
            "Always prefer accuracy over guesswork and never invent facts or unsupported statistics."
        ),
        llm=get_llm(),
        verbose=False,
    )

    explain_task = Task(
        description=(
            "Explain {topic} in 2-3 beginner-friendly sentences without invented statistics or unsupported claims."
        ),
        expected_output="A concise explanation in plain language for a beginner.",
        agent=teacher,
    )

    example_task = Task(
        description=(
            "Using the explanation from the previous step, create one practical example and one common misconception "
            "for {topic}. Clearly distinguish the example from the misconception."
        ),
        expected_output="One practical example and one common misconception, with a clear distinction between them.",
        agent=teacher,
        context=[explain_task],
    )

    quiz_task = Task(
        description=(
            "Using the explanation and example from the earlier steps, assemble the complete study guide for {topic}. "
            "Include the explanation, the example and misconception, then exactly three questions with a matching answer key."
        ),
        expected_output=(
            "A complete study guide with sections titled '## Explanation', '## Example and misconception', and '## Quiz'."
        ),
        agent=teacher,
        context=[explain_task, example_task],
    )

    return Crew(
        agents=[teacher],
        tasks=[explain_task, example_task, quiz_task],
        process=Process.sequential,
        verbose=False,
        tracing=False,
    )


def run_study_guide(topic: str) -> str:
    crew = build_crew(topic)
    result = crew.kickoff(inputs={"topic": topic})
    return str(result)


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]).strip() or "Model Context Protocol"
    try:
        output = run_study_guide(topic)
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1)

    print(output)
