import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")


class State(TypedDict):
    topic: str
    definition: str


llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    temperature=0,
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.environ["OPENROUTER_API_KEY"],
)


def define(state: State) -> State:
    """Generate a one-sentence definition for the topic."""
    prompt = (
        "Define the topic in exactly one sentence and do not use bullet points or lists. "
        f"Topic: {state['topic']}"
    )
    response = llm.invoke(prompt)
    state["definition"] = response.content.strip()
    return state


def format_output(state: State) -> State:
    """Wrap the produced definition with a simple output label."""
    state["definition"] = f"Definition: {state['definition']}"
    return state


def build_graph():
    graph = StateGraph(State)
    graph.add_node("define", define)
    graph.add_node("format_output", format_output)
    graph.set_entry_point("define")
    graph.add_edge("define", "format_output")
    graph.add_edge("format_output", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    result = app.invoke({"topic": "agentic AI", "definition": ""})
    print(result["definition"])
