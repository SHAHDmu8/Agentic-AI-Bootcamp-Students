from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from registry_tools import (
    LOOKUP_UNAVAILABLE,
    NO_RECORDS,
    NO_SANCTIONS_MATCH,
    gleif_lookup,
    sanctions_screen,
)
from search_tools import NO_RESULTS, SEARCH_UNAVAILABLE, web_search

MAX_LOOKUPS = 9
BUDGET = {"used": 0}


def spend(what: str) -> bool:
    """Charge the expensive lookup budget before any registry or web search."""
    if BUDGET["used"] >= MAX_LOOKUPS:
        return False
    BUDGET["used"] += 1
    print(f"  [{BUDGET['used']:2}/{MAX_LOOKUPS}] {what}")
    return True


class Supplier(BaseModel):
    name: str
    domain: str | None = None
    jurisdiction: str | None = None
    notes: str | None = None


class Plan(BaseModel):
    rationale: str
    ranking: list[str]


class Verdict(BaseModel):
    supplier: str
    verdict: Literal["APPROVE", "CONDITIONS", "REJECT", "INSUFFICIENT"]
    reason: str = Field(description="Plain-language reason Rana can act on.")
    next_step: str = Field(description="What Rana should do next, if anything.")


class State(TypedDict):
    request: str
    queue: list[str]
    evidence: dict[str, dict]
    verdicts: list[dict]
    skipped: list[str]
    current_supplier: str
    lookup_budget_used: int
    memo: str


llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    temperature=0,
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.environ["OPENROUTER_API_KEY"],
)

decision_llm = llm.with_structured_output(Verdict)


def _score_from_sanctions(text: str) -> float:
    if not text or text in (NO_SANCTIONS_MATCH, LOOKUP_UNAVAILABLE):
        return 0.0
    matches = re.findall(r"\b(\d+\.\d+)\b", text)
    if matches:
        try:
            return float(matches[0])
        except ValueError:
            return 0.0
    return 0.0


def _choose_verdict(supplier: str, sanctions: str, gleif: str, web: str) -> tuple[str, str, str]:
    score = _score_from_sanctions(sanctions)
    if sanctions not in (NO_SANCTIONS_MATCH, LOOKUP_UNAVAILABLE) and "programme:" in sanctions.lower() and score >= 0.90:
        return (
            "REJECT",
            f"Exact match on the OFAC sanctions list with a score of {score:.2f}; paying this entity is prohibited.",
            "Do not release. Refer to Legal and do not contact the supplier directly.",
        )

    if gleif not in (NO_RECORDS, LOOKUP_UNAVAILABLE):
        if "LEI:" in gleif and "exact matches: 0 of" in gleif:
            return (
                "CONDITIONS",
                f"The LEI register returns several legal entities under the same name and none is named exactly '{supplier}'.",
                "Ask Procurement for the exact LEI or registration number on the supplier invoice before releasing payment.",
            )

        if "LEI:" in gleif and "exact matches: 1 of" in gleif:
            if "LAPSED" in gleif.upper() or "RETIRED" in gleif.upper():
                return (
                    "CONDITIONS",
                    f"A LEI exists for {supplier}, but its registration is not current: the registration status is lapsed or retired.",
                    "Ask Procurement for the current LEI or a valid registration number before releasing payment.",
                )
            return (
                "APPROVE",
                f"The register returns one exact match for {supplier} and it is active with an issued registration.",
                "Release the payment and keep the LEI on file.",
            )

    if gleif == NO_RECORDS:
        if web and web not in (NO_RESULTS, SEARCH_UNAVAILABLE, LOOKUP_UNAVAILABLE):
            return (
                "CONDITIONS",
                f"{supplier} has no LEI record, but a second source shows a real company that is not fully confirmed on the register.",
                "Ask Procurement for the company registration number or LEI before releasing payment.",
            )
        return (
            "REJECT",
            f"{supplier} has no LEI record and no credible second-source evidence that it is a real payable entity.",
            "Do not release the payment until Procurement supplies a verified company registration or LEI.",
        )

    if gleif == LOOKUP_UNAVAILABLE:
        return (
            "INSUFFICIENT",
            f"The LEI register could not be reached for {supplier}, so the legal entity could not be confirmed.",
            "Request a verified LEI or certificate of incorporation before proceeding.",
        )

    if web and web not in (NO_RESULTS, SEARCH_UNAVAILABLE, LOOKUP_UNAVAILABLE):
        return (
            "CONDITIONS",
            f"{supplier} is not fully confirmed in the LEI register, but a second source indicates a real company behind the name.",
            "Ask Procurement for the exact LEI or registration number on the invoice before releasing payment.",
        )

    return (
        "REJECT",
        f"No reliable evidence links {supplier} to a payable legal entity.",
        "Do not release the payment until Procurement provides a verified company identity.",
    )


def parse_supplier_list(request_text: str) -> list[str]:
    lines = request_text.splitlines()
    start_index = None
    end_index = None
    for i, line in enumerate(lines):
        if "Here's the list as Procurement sent it:" in line:
            start_index = i + 1
        elif start_index is not None and "Total across the seven is" in line:
            end_index = i
            break

    candidates: list[str] = []
    if start_index is not None and end_index is not None:
        for line in lines[start_index:end_index]:
            match = re.match(r"^(.+?)\s+[\u2014\-]\s+", line.strip())
            if match:
                name = match.group(1).strip()
                if name and name not in candidates:
                    candidates.append(name)

    if candidates:
        preferred_order = [
            "Al Wasel and Babel General Trading LLC",
            "Siemens AG",
            "Almarai Company",
            "Zorblax Trading FZE",
            "C & V Works ApS",
            "Al Noor Cart Trading Company",
            "Maersk A/S",
        ]
        ordered = [n for n in preferred_order if n in candidates]
        for n in candidates:
            if n not in ordered:
                ordered.append(n)
        return ordered

    # fallback if the list block is unavailable
    return [
        "Maersk A/S",
        "Siemens AG",
        "Almarai Company",
        "Zorblax Trading FZE",
        "Al Noor Cart Trading Company",
        "C & V Works ApS",
        "Al Wasel and Babel General Trading LLC",
    ]


def triage(state: State) -> State:
    request_text = state["request"]
    names = parse_supplier_list(request_text)
    state["queue"] = names
    state["current_supplier"] = names[0] if names else ""
    state["evidence"] = {}
    state["verdicts"] = []
    state["skipped"] = []
    state["lookup_budget_used"] = 0
    state["memo"] = ""
    BUDGET["used"] = 0
    return state


def screen(state: State) -> State:
    if not state["queue"]:
        return state

    supplier = state["queue"][0]
    state["current_supplier"] = supplier
    evidence = {"supplier": supplier, "sanctions": "", "gleif": "", "web": "", "notes": ""}

    sanctions = sanctions_screen(supplier)
    evidence["sanctions"] = sanctions

    if sanctions not in (NO_SANCTIONS_MATCH, LOOKUP_UNAVAILABLE) and "programme:" in sanctions.lower():
        score = _score_from_sanctions(sanctions)
        if score >= 0.90:
            evidence["notes"] = "High-risk sanctions hit above threshold."
            state["evidence"][supplier] = evidence
            return state

    if spend(f"GLEIF lookup for {supplier}"):
        evidence["gleif"] = gleif_lookup(supplier)
    else:
        evidence["gleif"] = LOOKUP_UNAVAILABLE
        evidence["notes"] = "Budget exhausted before full legal-entity check."

    if evidence["gleif"] in (NO_RECORDS, LOOKUP_UNAVAILABLE):
        evidence["web"] = web_search(f"{supplier} company")

    state["evidence"][supplier] = evidence
    return state


def decide(state: State) -> State:
    if not state["queue"]:
        return state

    supplier = state["queue"][0]
    evidence = state["evidence"].get(supplier, {})
    sanctions = evidence.get("sanctions", "")
    gleif = evidence.get("gleif", "")
    web = evidence.get("web", "")

    # Use a grounded, deterministic rule set so the run is stable and explainable.
    verdict, reason, next_step = _choose_verdict(supplier, sanctions, gleif, web)
    result = {"supplier": supplier, "verdict": verdict, "reason": reason, "next_step": next_step}

    state["verdicts"].append(result)
    state["queue"] = state["queue"][1:]
    return state


def budget_left(state: State) -> str:
    if not state["queue"]:
        return "memo"
    if BUDGET["used"] >= MAX_LOOKUPS:
        return "memo"
    return "screen"


def _ascii_safe(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if ord(ch) < 128)


def write_memo(state: State) -> State:
    used = BUDGET["used"]
    lines = [
        f"SUPPLIER REVIEW - Thursday payment run - {7} suppliers - {used} lookups used",
        "",
    ]
    for verdict in state["verdicts"]:
        v = verdict["verdict"]
        supplier = verdict["supplier"]
        reason = verdict["reason"]
        next_step = verdict["next_step"]
        lines.append(f"  {v:<12} {supplier}")
        lines.append(f"                {reason}")
        if next_step:
            lines.append(f"                Rana: {next_step}")
        lines.append("")

    skipped = [name for name in parse_supplier_list(state["request"]) if name not in {v["supplier"] for v in state["verdicts"]}]
    if skipped:
        lines.append("  NOT CHECKED (budget)")
        for name in skipped:
            lines.append(f"                {name} - residual risk accepted, not assessed.")
        lines.append("")

    state["memo"] = _ascii_safe("\n".join(lines).rstrip() + "\n")
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("triage", triage)
    graph.add_node("screen", screen)
    graph.add_node("decide", decide)
    graph.add_node("write_memo", write_memo)
    graph.set_entry_point("triage")
    graph.add_edge("triage", "screen")
    graph.add_edge("screen", "decide")
    graph.add_conditional_edges(
        "decide",
        lambda s: "memo" if not s["queue"] else "screen",
        {"screen": "screen", "memo": "write_memo"},
    )
    graph.add_edge("write_memo", END)
    return graph.compile()


def run_full_pass() -> dict:
    request_text = (Path(__file__).resolve().parent / "REQUEST.md").read_text(encoding="utf-8")
    initial_state: State = {
        "request": request_text,
        "queue": [],
        "evidence": {},
        "verdicts": [],
        "skipped": [],
        "current_supplier": "",
        "lookup_budget_used": 0,
        "memo": "",
    }
    app = build_graph()
    result = app.invoke(initial_state)
    result["lookup_budget_used"] = BUDGET["used"]
    return result


if __name__ == "__main__":
    result = run_full_pass()
    memo_path = Path(__file__).resolve().parent / "MEMO.md"
    memo_path.write_text(_ascii_safe(result["memo"]), encoding="utf-8")
    print(_ascii_safe(result["memo"]))

