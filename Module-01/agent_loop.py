import ast
import json
import os
import re
from pathlib import Path

from openai import OpenAI

MAX_STEPS = 6
MODEL = "openai/gpt-4o-mini"
BASE_URL = "https://openrouter.ai/api/v1"


def _load_root_env() -> None:
    """Read the repository root .env file if it exists and the key is not already set."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_root_env()


SYSTEM_PROMPT = """\
You are an autonomous agent solving a problem step by step.
You CANNOT do arithmetic yourself; you must use the `calculator` tool.
Use the calculator tool for any arithmetic needed.
Use the observation history to decide the next step. If a number or intermediate result is already known, build on it instead of repeating the same calculation.
Do not repeat the same calculator expression twice.
When you produce a final_answer, include the full result in a sentence such as: "537, yes, more than 500."
You must return ONLY valid JSON, with no prose and no markdown code fences.
Use exactly one of these shapes:
{"action": "calculator", "args": {"expr": "<expression>"}}
{"action": "final_answer", "args": {"text": "<answer>"}}
"""


def calculator(expr: str) -> str:
    """Safely evaluate a simple arithmetic expression and return the result."""
    if not isinstance(expr, str):
        raise ValueError("Expression must be a string.")

    expr = expr.strip()
    if not expr:
        raise ValueError("Expression is empty.")

    if re.search(r"[^0-9+\-*/().\s]", expr):
        raise ValueError("Expression contains unsupported characters.")

    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid arithmetic expression: {expr}") from exc

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                raise ValueError("Boolean literals are not allowed.")
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
            value = evaluate(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    result = evaluate(parsed)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


def call_model(messages: list) -> str:
    """Send messages to the LLM and return the raw text content of the reply."""
    return call_model_with_usage(messages)["content"]


def call_model_with_usage(messages: list) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Add it to the root .env file or your environment.")

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    completion = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
    )

    content = completion.choices[0].message.content or ""
    usage = getattr(completion, "usage", None)
    usage_payload = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
    return {"content": content, "usage": usage_payload}


def parse_action(raw: str) -> dict:
    """Parse the model's JSON action. Strips markdown fences and stray text if present."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Received empty model output.")

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return json.loads(text)


def run_agent(question: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    llm_calls = 0
    total_tokens = 0
    last_action = None

    for step in range(1, MAX_STEPS + 1):
        response = call_model_with_usage(messages)
        llm_calls += 1
        total_tokens += response["usage"].get("total_tokens", 0)

        raw_action = response["content"]
        action = parse_action(raw_action)
        action_name = action.get("action")

        if action_name == "final_answer":
            final_text = str(action.get("args", {}).get("text", ""))
            print(f"[step {step}] final_answer: {final_text}")
            print(f"[summary] steps={step} llm_calls={llm_calls} total_tokens={total_tokens}")
            return final_text

        if action_name == "calculator":
            expr = str(action.get("args", {}).get("expr", ""))
            if last_action == expr:
                print(f"[stopped] repeated calculator action: {expr}")
                print(f"[summary] steps={step - 1} llm_calls={llm_calls} total_tokens={total_tokens}")
                return "No final answer (repeated action)."
            result = calculator(expr)
            print(f"[step {step}] calculator: {expr} = {result}")
            messages.append({"role": "user", "content": f"Observation: {result}"})
            last_action = expr
            continue

        raise ValueError(f"Unsupported action: {action_name!r}")

    print(f"[stopped] step budget exhausted. steps={MAX_STEPS} llm_calls={llm_calls} total_tokens={total_tokens}")
    return "No final answer (budget exhausted)."


if __name__ == "__main__":
    q = "What is (23 * 19) + 100, and is that more than 500?"
    print(run_agent(q))
