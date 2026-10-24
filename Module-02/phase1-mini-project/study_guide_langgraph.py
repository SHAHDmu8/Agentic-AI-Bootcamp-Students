from __future__ import annotations

import os
import sys
from typing import TypedDict

from dotenv import find_dotenv, load_dotenv
from langgraph.graph import END, StateGraph
from langchain_openai import ChatOpenAI

load_dotenv()
load_dotenv(find_dotenv(usecwd=True))

llm = None


class StudyGuideState(TypedDict):
    topic: str
    explanation: str
    example: str
    quiz: str


def get_llm() -> ChatOpenAI:
    """Create the shared OpenRouter-backed LLM client."""
    global llm
    if llm is not None:
        return llm

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found. Add it to the repo root .env file before running this script."
        )

    llm = ChatOpenAI(
        model="dots-studio/dots-3-note-preview:free",
        temperature=0,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return llm


def explain_topic(state: StudyGuideState) -> StudyGuideState:
    """Create a beginner-friendly explanation for the topic."""
    response = get_llm().invoke(
        (
            f"Explain the topic '{state['topic']}' in 2-3 plain-language sentences for a beginner. "
            "Do not invent statistics, and do not include a quiz yet."
        )
    )
    return {**state, "explanation": response.content.strip()}


def create_example(state: StudyGuideState) -> StudyGuideState:
    """Create a practical example and common misconception using the topic and explanation."""
    response = get_llm().invoke(
        (
            f"Using the topic '{state['topic']}' and the explanation below, provide one practical example, "
            "one common misconception, and a clear distinction between them.\n\n"
            f"Explanation:\n{state['explanation']}"
        )
    )
    return {**state, "example": response.content.strip()}


def create_quiz(state: StudyGuideState) -> StudyGuideState:
    """Create exactly three questions and a matching answer key using the full context."""
    response = get_llm().invoke(
        (
            f"Create a study guide quiz for the topic '{state['topic']}'. "
            "Use the explanation and example below to create exactly three questions and a matching answer key. "
            "Each question should be clear for a beginner and the final answer key should match the questions exactly.\n\n"
            f"Explanation:\n{state['explanation']}\n\nExample:\n{state['example']}"
        )
    )
    return {**state, "quiz": response.content.strip()}


def build_graph():
    graph = StateGraph(StudyGuideState)
    graph.add_node("explain_topic", explain_topic)
    graph.add_node("create_example", create_example)
    graph.add_node("create_quiz", create_quiz)
    graph.set_entry_point("explain_topic")
    graph.add_edge("explain_topic", "create_example")
    graph.add_edge("create_example", "create_quiz")
    graph.add_edge("create_quiz", END)
    return graph.compile()


def format_study_guide(result: StudyGuideState) -> str:
    return (
        f"# Study Guide: {result['topic']}\n\n"
        "## Explanation\n"
        f"{result['explanation']}\n\n"
        "## Example and misconception\n"
        f"{result['example']}\n\n"
        "## Quiz\n"
        f"{result['quiz']}"
    )


def run_study_guide(topic: str) -> StudyGuideState:
    app = build_graph()
    initial_state: StudyGuideState = {
        "topic": topic,
        "explanation": "",
        "example": "",
        "quiz": "",
    }
    return app.invoke(initial_state)


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]).strip() or "Model Context Protocol"
    try:
        result = run_study_guide(topic)
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1)

    print(format_study_guide(result))
