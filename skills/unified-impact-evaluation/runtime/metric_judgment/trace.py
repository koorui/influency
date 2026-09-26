from __future__ import annotations

import re
import threading
import time
from typing import Any


class TracingLLMClient:
    """Transparent audit wrapper around production LLMClient.chat_json."""

    def __init__(self, inner: Any, *, stage: str = "g_level_direct_judgment"):
        self.inner = inner
        self.settings = inner.settings
        self.stage = stage
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._next_call_id = 1

    @property
    def available(self) -> bool:
        return bool(self.inner.available)

    def chat_json(self, system: str, user: str, **kwargs: Any):
        trace_stage = str(kwargs.pop("_trace_stage", self.stage))
        trace_unit = str(kwargs.pop("_trace_unit", ""))
        with self._lock:
            call_number = self._next_call_id
            self._next_call_id += 1
        model = str(kwargs.get("model") or self.settings.glm_model)
        temperature = float(kwargs.get("temperature", 0.1))
        expect = str(kwargs.get("expect", "object"))
        provider_request = bool(self.available)
        started = time.perf_counter()
        result = self.inner.chat_json(system, user, **kwargs)
        elapsed = round(time.perf_counter() - started, 4)
        metric_match = re.search(r'"metric_id"\s*:\s*"([^"]+)"', user)
        call = {
            "call_id": f"CALL-{call_number:03d}",
            "stage": trace_stage,
            "unit_id": trace_unit,
            "metric_id": trace_unit or (metric_match.group(1) if metric_match else ""),
            "status": "completed" if result.ok else "failed",
            "transport": "provider" if provider_request else "disabled",
            "provider_request": provider_request,
            "elapsed_seconds": elapsed,
            "request": {
                "model": model,
                "temperature": temperature,
                "expect": expect,
                "max_attempts": int(kwargs.get("max_attempts", 3)),
                "timeout": kwargs.get("timeout"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            "response": {
                "model": str(result.model or model),
                "raw_text": str(result.text or result.raw or ""),
                "parsed_json": result.data,
                "error_type": str(result.error_type or ""),
                "error": str(result.error or ""),
            },
        }
        with self._lock:
            self.calls.append(call)
        print(
            f"[indicator-llm] {call['call_id']} {trace_stage} {trace_unit} "
            f"{call['status']} {elapsed:.1f}s",
            flush=True,
        )
        return result

    def reject_response(self, unit_id: str, error: str) -> None:
        """Retain the raw response but exclude malformed output from success counts."""
        with self._lock:
            for call in reversed(self.calls):
                if call['unit_id'] == unit_id and call['status'] == 'completed':
                    call['status'] = 'failed'
                    call['response']['error_type'] = 'ModelOutputSchemaError'
                    call['response']['error'] = error
                    return

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            calls = sorted(self.calls, key=lambda row: int(str(row["call_id"]).split("-")[-1]))
        stage_breakdown: dict[str, dict[str, Any]] = {}
        for call in calls:
            stage_id = str(call.get("stage") or "UNKNOWN").split("_", 1)[0]
            bucket = stage_breakdown.setdefault(
                stage_id,
                {"call_count": 0, "successful_call_count": 0, "failed_call_count": 0, "elapsed_seconds": 0.0},
            )
            bucket["call_count"] += 1
            bucket["successful_call_count"] += int(call["status"] == "completed")
            bucket["failed_call_count"] += int(call["status"] == "failed")
            bucket["elapsed_seconds"] = round(bucket["elapsed_seconds"] + float(call.get("elapsed_seconds") or 0), 4)
        return {
            "summary": {
                "call_count": len(calls),
                "provider_request_count": sum(bool(call["provider_request"]) for call in calls),
                "successful_call_count": sum(call["status"] == "completed" for call in calls),
                "failed_call_count": sum(call["status"] == "failed" for call in calls),
                "models": list(dict.fromkeys(call["response"]["model"] for call in calls if call["response"]["model"])),
                "stage_breakdown": stage_breakdown,
            },
            "calls": calls,
        }

__all__ = ["TracingLLMClient"]
