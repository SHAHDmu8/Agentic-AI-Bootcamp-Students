import ast
import json
import os
import re
from pathlib import Path

from openai import OpenAI

MAX_STEPS = 6
MAX_LLM_CALLS = 8
MODEL = "openai/gpt-4o-mini"
BASE_URL = "https://openrouter.ai/api/v1"

COUNTRY_CAPITALS = {
    "france": "Paris",
    "germany": "Berlin",
    "italy": "Rome",
    "spain": "Madrid",
    "united kingdom": "London",
    "uk": "London",
    "canada": "Ottawa",
    "japan": "Tokyo",
    "india": "New Delhi",
    "egypt": "Cairo",
    "morocco": "Rabat",
    "tunisia": "Tunis",
}


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
You must choose exactly one action on each step.
Use the `calculator` tool for arithmetic only.
Use the `lookup` tool for country-to-capital facts only.
Use the `final_answer` tool only when the user question is fully answered.
Do not repeat the same tool action and arguments twice in a row.
If a value is already known, reuse it instead of repeating the same step.
You must return ONLY valid JSON, with no prose and no markdown code fences.
Use exactly one of these shapes:
{"action": "calculator", "args": {"expr": "<expression>"}}
{"action": "lookup", "args": {"country": "<country>"}}
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


def lookup(country: str) -> str:
    """Return the capital for a supported country. Raise a helpful error for unknown values."""
    if not isinstance(country, str):
        raise ValueError("Country must be a string.")

    cleaned = country.strip()
    if not cleaned:
        raise ValueError("Country is empty.")

    capital = COUNTRY_CAPITALS.get(cleaned.lower())
    if capital is None:
        raise ValueError(f"Unsupported country: {country}")
    return capital


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
    last_tool_signature = None

    for step in range(1, MAX_STEPS + 1):
        if llm_calls >= MAX_LLM_CALLS:
            print(f"[stopped] llm call budget exhausted. llm_calls={llm_calls} total_tokens={total_tokens}")
            return "No final answer (budget exhausted)."

        response = call_model_with_usage(messages)
        llm_calls += 1
        total_tokens += response["usage"].get("total_tokens", 0)

        raw_action = response["content"]
        try:
            action = parse_action(raw_action)
        except (ValueError, json.JSONDecodeError, TypeError):
            if llm_calls >= MAX_LLM_CALLS:
                print(f"[stopped] llm call budget exhausted. llm_calls={llm_calls} total_tokens={total_tokens}")
                return "No final answer (budget exhausted)."

            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Return ONLY valid JSON in one of these exact shapes: "
                '{"action": "calculator", "args": {"expr": "<expression>"}}; '
                '{"action": "lookup", "args": {"country": "<country>"}}; '
                '{"action": "final_answer", "args": {"text": "<answer>"}}'
            )
            messages.append({"role": "user", "content": retry_prompt})
            response = call_model_with_usage(messages)
            llm_calls += 1
            total_tokens += response["usage"].get("total_tokens", 0)
            raw_action = response["content"]
            try:
                action = parse_action(raw_action)
            except (ValueError, json.JSONDecodeError, TypeError) as exc:
                raise ValueError("Model failed to return valid JSON even after one retry.") from exc

        action_name = action.get("action")
        args = action.get("args", {}) or {}

        if action_name == "final_answer":
            final_text = str(args.get("text", ""))
            print(f"[step {step}] final_answer: {final_text}")
            print(f"[summary] steps={step} llm_calls={llm_calls} total_tokens={total_tokens}")
            return final_text

        if action_name not in {"calculator", "lookup"}:
            raise ValueError(f"Unsupported action: {action_name!r}")

        tool_signature = (action_name, json.dumps(args, sort_keys=True))
        if last_tool_signature == tool_signature:
            print(f"[stopped] repeated tool action: {action_name} {args}")
            print(f"[summary] steps={step - 1} llm_calls={llm_calls} total_tokens={total_tokens}")
            return "No final answer (repeated action)."

        if action_name == "calculator":
            expr = str(args.get("expr", ""))
            result = calculator(expr)
            print(f"[step {step}] calculator: {expr} = {result}")
            messages.append({"role": "user", "content": f"Observation: {result}"})
        elif action_name == "lookup":
            country = str(args.get("country", ""))
            result = lookup(country)
            print(f"[step {step}] lookup: {country} = {result}")
            messages.append({"role": "user", "content": f"Observation: {result}"})

        last_tool_signature = tool_signature
        continue

    print(f"[stopped] step budget exhausted. steps={MAX_STEPS} llm_calls={llm_calls} total_tokens={total_tokens}")
    return "No final answer (budget exhausted)."


if __name__ == "__main__":
    if os.environ.get("OPENROUTER_API_KEY"):
        q = "What is the capital of France, and what is 12 * 12?"
        print(run_agent(q))
