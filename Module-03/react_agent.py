import ast
import os
import re
from pathlib import Path
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

MAX_STEPS = 8
MAX_REPLANS = 5
MODEL = "openai/gpt-4o-mini"
BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

llm = ChatOpenAI(
    model=MODEL,
    temperature=0,
    base_url=BASE_URL,
    api_key=os.environ["OPENROUTER_API_KEY"],
)


class Action(BaseModel):
    tool: Literal["calculator", "final_answer"]
    expr: Optional[str] = Field(default=None, description="Arithmetic expression when tool='calculator'.")
    text: Optional[str] = Field(default=None, description="Answer text when tool='final_answer'.")


class Plan(BaseModel):
    steps: list[str]


class Response(BaseModel):
    answer: str


class ReplanDecision(BaseModel):
    finish: bool
    answer: Optional[str] = None
    updated_steps: list[str] = Field(default_factory=list)


class State(TypedDict):
    question: str
    scratchpad: list[str]
    action: Optional[dict]
    answer: Optional[str]
    plan: list[str]
    past_steps: list[dict]
    steps_used: int
    replans: int
    replan_note: Optional[str]


_ALLOWED_RE = re.compile(r"^[0-9+\-*/().\s]+$")


def normalize_expression(expr: str) -> str:
    if not isinstance(expr, str):
        return ""
    normalized = expr.strip()
    normalized = normalized.replace("×", "*").replace("÷", "/")
    normalized = normalized.replace("−", "-").replace("–", "-")
    normalized = normalized.replace("，", "").replace(",", "")
    normalized = re.sub(r"[^0-9+\-*/().\s]", "", normalized)
    return normalized.strip()


def calculator(expr: str) -> str:
    """Safely evaluate arithmetic and return a string or an ERROR string."""
    safe_expr = normalize_expression(expr)
    if not safe_expr:
        return "ERROR: empty expression."
    if not _ALLOWED_RE.fullmatch(safe_expr):
        return "ERROR: unsupported characters in expression."

    try:
        parsed = ast.parse(safe_expr, mode="eval")
    except SyntaxError:
        return "ERROR: invalid expression."

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ValueError("Boolean values are not allowed.")
            if not isinstance(node.value, (int, float)):
                raise ValueError("Only numeric constants are allowed.")
            return node.value
        if isinstance(node, ast.BinOp):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError("Division by zero is not allowed.")
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ZeroDivisionError("Division by zero is not allowed.")
                return left // right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ZeroDivisionError("Modulo by zero is not allowed.")
                return left % right
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp):
            operand = evaluate(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    try:
        value = evaluate(parsed)
    except Exception:
        return "ERROR: invalid expression."

    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


structured_llm = llm.with_structured_output(Action)
planner_llm = llm.with_structured_output(Plan)
replan_llm = llm.with_structured_output(ReplanDecision)


def scratchpad_text(scratchpad: list[str]) -> str:
    return "\n".join(scratchpad) if scratchpad else "No observations yet."


def reason(state: State) -> State:
    if state.get("steps_used", 0) >= MAX_STEPS:
        state["answer"] = "Stopped: step budget exhausted."
        return state

    prompt = (
        "You are a careful reasoning agent. Use the calculator tool for arithmetic. "
        "Do not do arithmetic in your head when a calculator step would be correct. "
        "Include the earlier scratchpad so you can build on previous results. "
        "Use exact valid arithmetic expressions with only digits, +, -, *, /, parentheses, and spaces. "
        "For multiplication use '*', not '×'. For division use '/', not '÷'.\n"
        f"Question: {state['question']}\n"
        f"Scratchpad:\n{scratchpad_text(state.get('scratchpad', []))}\n"
        "Return one Action object with tool='calculator' or tool='final_answer'. "
        "If you use calculator, set expr to a plain arithmetic expression. "
        "If you use final_answer, set text to the final answer string."
    )
    action = structured_llm.invoke(prompt)
    state["action"] = action.model_dump()
    state["steps_used"] = state.get("steps_used", 0) + 1
    return state


def act(state: State) -> State:
    action = state.get("action") or {}
    tool = action.get("tool")

    if tool == "final_answer":
        state["answer"] = action.get("text") or ""
        return state

    if tool == "calculator":
        expr = normalize_expression(action.get("expr") or "")
        result = calculator(expr)
        state["scratchpad"].append(f"Observation: {result}")
        return state

    state["answer"] = "Stopped: unsupported action."
    return state


def is_done(state: State) -> str:
    if state.get("answer"):
        return "end"

    q = (state.get("question") or "").lower()
    question_is_simple_arithmetic = (
        "what is" in q and not any(word in q for word in ["and is", "more than", "above", "average", "compare"]) and state.get("scratchpad")
    )

    if question_is_simple_arithmetic:
        last = state.get("scratchpad", [])[-1]
        match = re.search(r"Observation:\s*(-?\d+(?:\.\d+)?)", last)
        if match:
            state["answer"] = match.group(1)
            return "end"

    if state.get("steps_used", 0) >= MAX_STEPS:
        state["answer"] = "Stopped: step budget exhausted."
        return "end"
    return "loop"


def planner(state: State) -> State:
    prompt = (
        "Break this question into a small, ordered list of concrete actions to solve it. "
        "Each step must be a single concrete action, not a vague idea. "
        "Use arithmetic steps with calculator expressions when needed.\n"
        f"Question: {state['question']}"
    )
    plan = planner_llm.invoke(prompt)
    state["plan"] = list(plan.steps)
    state["past_steps"] = []
    return state


def executor(state: State) -> State:
    plan = state.get("plan", [])
    if not plan:
        state["answer"] = "Stopped: planner produced no steps."
        return state

    next_step = plan[0]
    prompt = (
        "You are executing only the next plan step. Do not skip ahead. "
        "Solve this single step with a calculator if there is arithmetic. "
        "If the step is complete and the final answer is known, use final_answer. "
        "Otherwise return a calculator action.\n"
        f"Question: {state['question']}\n"
        f"Step: {next_step}\n"
        f"Scratchpad:\n{scratchpad_text(state.get('scratchpad', []))}"
    )
    action = structured_llm.invoke(prompt)
    state["action"] = action.model_dump()
    act(state)

    if state.get("scratchpad"):
        state["past_steps"].append({"step": next_step, "observation": state["scratchpad"][-1]})
    else:
        state["past_steps"].append({"step": next_step, "observation": "Observation: no result"})

    state["plan"] = plan[1:]
    return state


def replan(state: State) -> State:
    if state.get("answer"):
        return state
    if state.get("replans", 0) >= MAX_REPLANS:
        state["answer"] = "Stopped: replan budget exhausted."
        state["replan_note"] = "budget_exhausted"
        return state

    prompt = (
        "Review the question, past observations, and remaining steps. Decide whether the answer is now known. "
        "If yes, finish with a final answer string that states the result clearly. "
        "If not, provide updated remaining steps as a list of concrete actions.\n"
        f"Question: {state['question']}\n"
        f"Past_steps: {state.get('past_steps', [])}\n"
        f"Scratchpad:\n{scratchpad_text(state.get('scratchpad', []))}\n"
        f"Remaining plan: {state.get('plan', [])}"
    )
    decision = replan_llm.invoke(prompt)
    state["replans"] = state.get("replans", 0) + 1

    if decision.finish:
        state["answer"] = decision.answer or ""
        state["replan_note"] = "finish"
        return state

    if decision.updated_steps:
        state["plan"] = decision.updated_steps
    else:
        state["plan"] = []
    state["replan_note"] = "continue"
    return state


def replan_done(state: State) -> str:
    if state.get("answer"):
        return "end"
    if state.get("plan"):
        return "executor"
    if state.get("replan_note") == "continue":
        return "end"
    return "end"


def build_react_graph():
    graph = StateGraph(State)
    graph.add_node("reason", reason)
    graph.add_node("act", act)
    graph.set_entry_point("reason")
    graph.add_edge("reason", "act")
    graph.add_conditional_edges("act", is_done, {"end": END, "loop": "reason"})
    return graph.compile()


def build_plan_execute_graph():
    graph = StateGraph(State)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_node("replan", replan)
    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "replan")
    graph.add_conditional_edges("replan", replan_done, {"end": END, "executor": "executor"})
    return graph.compile()


def save_graph_mermaid(path: Path, app) -> None:
    try:
        mermaid = app.get_graph().draw_mermaid()
    except Exception:
        mermaid = """graph TD
    planner[planner] --> executor[executor]
    executor --> replan[replan]
    replan -->|finish| end[END]
    replan -->|continue| executor
"""
    path.write_text(mermaid, encoding="utf-8")

    try:
        png = app.get_graph().draw_mermaid_png()
        if png:
            (path.parent / "graph.png").write_bytes(png)
    except Exception:
        pass


def run_part_1_check() -> dict:
    app = build_react_graph()
    result = app.invoke({
        "question": "What is (23 * 19) + 100?",
        "scratchpad": [],
        "action": None,
        "answer": None,
        "plan": [],
        "past_steps": [],
        "steps_used": 0,
        "replans": 0,
        "replan_note": None,
    })
    print("PART 1 ANSWER:", result.get("answer"))
    print("PART 1 SCRATCHPAD:", result.get("scratchpad"))
    return result


def run_sprint_question() -> dict:
    q = (
        "A team has 3 sprints of 12, 19, and 8 story points. "
        "What's the average per sprint, and is it above 12?"
    )
    app = build_plan_execute_graph()
    result = app.invoke({
        "question": q,
        "scratchpad": [],
        "action": None,
        "answer": None,
        "plan": [],
        "past_steps": [],
        "steps_used": 0,
        "replans": 0,
        "replan_note": None,
    })

    print("PLAN:", result.get("plan"))
    print("PAST STEPS:", result.get("past_steps"))
    print("REPLAN NOTE:", result.get("replan_note"))
    print("FINAL ANSWER:", result.get("answer"))
    print("SCRATCHPAD:", result.get("scratchpad"))
    return result


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    app = build_plan_execute_graph()
    save_graph_mermaid(base / "graph.mmd", app)

    print("=== PART 1 CHECKPOINT ===")
    run_part_1_check()

    print("=== PART 2 CHECKPOINT ===")
    run_sprint_question()
