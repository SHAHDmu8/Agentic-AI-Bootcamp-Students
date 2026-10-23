import os
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")


llm = LLM(
    model="openai/gpt-4o-mini",
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)


def build_crew() -> Crew:
    definer = Agent(
        role="Concise Encyclopedia",
        goal="Define topics clearly and accurately in a single sentence.",
        backstory=(
            "You are a careful encyclopedia editor who explains technical ideas in plain language "
            "without jargon or lists."
        ),
        llm=llm,
        verbose=True,
    )

    define_task = Task(
        description="Define {topic} in exactly one sentence.",
        expected_output="A single-sentence definition of the topic.",
        agent=definer,
    )

    return Crew(
        agents=[definer],
        tasks=[define_task],
        process=Process.sequential,
        verbose=True,
    )


if __name__ == "__main__":
    crew = build_crew()
    result = crew.kickoff(inputs={"topic": "agentic AI"})
    print(result)
