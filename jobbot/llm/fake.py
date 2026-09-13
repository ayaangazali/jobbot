"""Fake LLM provider for locked tests: reads scripted responses from disk.

Script format: a JSON object with tool_name → response entries, or phases.
A test sets `JOBBOT_FAKE_LLM` env var to point at the script file, and
`JOBBOT_FAKE_LLM_LOG` for a call log (newline-delimited JSON).

Minimal implementation: every call returns the same response regardless of
input, matching only the tool and phase keys in the script. No retries, no
streamed tokens—responses are instant and final.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


@dataclass
class FakeLLMResponse:
    text: str
    tool_input: dict[str, Any] | None = None
    thinking: str = ""
    input_tokens: int = 1
    output_tokens: int = 1
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class FakeLLM:
    """Scripted LLM that reads responses from a JSON file on each call."""

    def __init__(self, script_path: str | Path, log_path: str | Path | None = None):
        self.script_path = Path(script_path)
        self.log_path = Path(log_path) if log_path else None
        self._load_script()

    def _load_script(self) -> None:
        try:
            if self.script_path.exists():
                self.script = json.loads(self.script_path.read_text())
            else:
                self.script = {}
        except Exception as exc:
            log.error("fake_llm_script_load_error", path=self.script_path, error=str(exc))
            self.script = {}

    def _log_call(self, payload: dict[str, Any]) -> None:
        if not self.log_path:
            return
        entry = {**payload, "timestamp": json.loads(json.dumps(payload)).__class__.__name__}
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.error("fake_llm_log_write_error", path=self.log_path, error=str(exc))

    def call(
        self,
        *,
        system: str | list[dict[str, Any]] | None = None,
        blocks: list[dict[str, Any]],
        tool: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> FakeLLMResponse:
        """Minimal call interface matching LLMClient.call signature.

        Looks up response by tool name if present, otherwise returns a default.
        """
        self._load_script()  # Re-read on each call so tests can hotswap

        tool_name = tool.get("name") if tool else None
        key = tool_name or "default"

        # Try exact key, then fallback to default
        response_spec = self.script.get(key, self.script.get("default"))

        # Log the call
        self._log_call({
            "tool": tool_name,
            "blocks_count": len(blocks),
            "system_present": system is not None,
            "max_tokens": max_tokens,
        })

        if not response_spec:
            return FakeLLMResponse(
                text=f"[FAKE] no response for tool {key!r}",
                tool_input=None,
            )

        # response_spec may be {"text": "...", "tool_input": {...}} or just a string
        if isinstance(response_spec, str):
            return FakeLLMResponse(text=response_spec, tool_input=None)
        elif isinstance(response_spec, dict):
            return FakeLLMResponse(
                text=response_spec.get("text", ""),
                tool_input=response_spec.get("tool_input"),
                thinking=response_spec.get("thinking", ""),
                input_tokens=response_spec.get("input_tokens", 1),
                output_tokens=response_spec.get("output_tokens", 1),
                cache_read_tokens=response_spec.get("cache_read_tokens", 0),
                cache_write_tokens=response_spec.get("cache_write_tokens", 0),
            )
        else:
            return FakeLLMResponse(text=f"[FAKE] invalid response spec: {response_spec!r}")

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}

    def quota(self) -> dict[str, Any] | None:
        return None
