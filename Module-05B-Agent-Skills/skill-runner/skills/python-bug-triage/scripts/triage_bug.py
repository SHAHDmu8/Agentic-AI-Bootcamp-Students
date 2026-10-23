import json
import re
import sys
from typing import Any

SEVERITY_RULES = {
    "SEV1": [
        "crash",
        "data loss",
        "outage",
        "production down",
        "auth bypass",
        "security",
        "traceback",
        "segmentation fault",
    ],
    "SEV2": [
        "major regression",
        "broken primary path",
        "500",
        "internal server error",
        "all users",
        "unable to login",
        "cannot create",
    ],
    "SEV3": [
        "workaround",
        "partial failure",
        "some users",
        "slow",
        "degraded",
        "timeout",
        "warning",
    ],
    "SEV4": [
        "cosmetic",
        "typo",
        "minor",
        "nuisance",
        "small issue",
    ],
}

REQUIRED_FIELDS = [
    "expected",
    "actual",
    "steps",
    "environment",
    "version",
]


def lower_text(text: str) -> str:
    return text.lower()


def detect_severity(text: str) -> str:
    low = lower_text(text)
    for severity, phrases in SEVERITY_RULES.items():
        if any(phrase in low for phrase in phrases):
            return severity
    return "SEV3"


def find_component(text: str) -> str:
    patterns = [
        r"component[:\s]+([A-Za-z0-9_./\- ]+)",
        r"module[:\s]+([A-Za-z0-9_./\- ]+)",
        r"service[:\s]+([A-Za-z0-9_./\- ]+)",
        r"in ([A-Za-z0-9_./\-]+)\.(?:py|js|ts)",
        r"\b(?:api|agent|llm|db|auth|ui|worker|parser|server|cache)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip() if match.lastindex else match.group(0).strip()
    return "not specified"


def find_missing_fields(text: str) -> list[str]:
    low = lower_text(text)
    missing = []
    if "expected" not in low and "should" not in low and "expected result" not in low:
        missing.append("expected result")
    if "actual" not in low and "got" not in low and "observed" not in low:
        missing.append("actual result")
    if "steps" not in low and "reproduce" not in low and "how to reproduce" not in low:
        missing.append("reproduction steps")
    if "version" not in low and "commit" not in low and "release" not in low:
        missing.append("version or environment")
    if "environment" not in low and "os" not in low and "windows" not in low and "linux" not in low:
        missing.append("environment")
    return missing


def build_report(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    report = {
        "severity": detect_severity(text),
        "likely_component": find_component(text),
        "missing_facts": find_missing_fields(text),
        "next_action": "Ask for missing reproduction details or validate the issue in a clean environment.",
    }
    return report


def main() -> None:
    raw_text = sys.stdin.read().strip()
    if not raw_text:
        print(json.dumps({"error": "No bug report provided on stdin."}, indent=2))
        return

    result = build_report(raw_text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
