import importlib.util
import os
import sys
from pathlib import Path

import tiktoken

MODULE_PATH = Path(__file__).resolve().parent / "starter-code" / "memory_agent.py"
spec = importlib.util.spec_from_file_location("memory_agent_mod", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MockLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if isinstance(messages, str):
            return type("Resp", (), {"content": "mock summary"})()
        return type("Resp", (), {"content": "mock summary from llm"})()


def test_summary_trigger_and_fold():
    original_llm = mod.llm
    try:
        mock_llm = MockLLM()
        mod.llm = mock_llm
        stm = mod.ShortTermMemory()

        enc = tiktoken.get_encoding("o200k_base")
        turns = [
            ("user", "one"),
            ("assistant", "two"),
            ("user", "three"),
            ("assistant", "four"),
            ("user", "five"),
            ("assistant", "six"),
            ("user", "seven"),
        ]

        for role, text in turns:
            stm.add(role, text)

        raw_before = len(enc.encode("\n".join(f"{role}: {text}" for role, text in turns)))
        folded_after_first = len(enc.encode(stm.context()))

        assert len(stm.buffer) == 4, f"expected 4 buffered turns after 7th turn, got {len(stm.buffer)}"
        assert stm.summary_source == "llm", f"expected llm summary, got {stm.summary_source}"
        assert stm.summary, "summary should not be empty"
        assert folded_after_first < raw_before, (
            f"expected folded context smaller than raw transcript; got {folded_after_first} vs {raw_before}"
        )
        assert len(mock_llm.calls) >= 1, "LLM summarization should have been called"

        for role, text in [("assistant", "eight"), ("user", "nine"), ("assistant", "ten")]:
            stm.add(role, text)

        assert len(stm.buffer) == 4, f"expected 4 buffered turns after second fold, got {len(stm.buffer)}"
        assert stm.summary, "summary should still exist after second fold"
        assert "mock summary" in stm.summary, "summary should be retained and updated"

        second_raw = len(enc.encode("\n".join(f"{role}: {text}" for role, text in turns + [("assistant", "eight"), ("user", "nine"), ("assistant", "ten")]) ))
        second_folded = len(enc.encode(stm.context()))
        assert second_folded < second_raw, (
            f"expected second folded context to remain smaller than raw transcript; got {second_folded} vs {second_raw}"
        )

        print("SUMMARY_TEST_PASS")
        print(f"raw_before={raw_before}")
        print(f"folded_after_first={folded_after_first}")
        print(f"second_raw={second_raw}")
        print(f"second_folded={second_folded}")
        print(f"buffer_after_second_fold={len(stm.buffer)}")
        print(f"summary_source={stm.summary_source}")
        print(f"summary={stm.summary}")
        print(f"llm_calls={len(mock_llm.calls)}")
    finally:
        mod.llm = original_llm


def main():
    test_summary_trigger_and_fold()


if __name__ == "__main__":
    main()
