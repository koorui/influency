from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

from impact_eval.llm import LLMClient as ProductionLLMClient
from impact_eval.llm import LLMResult, _extract_json


class LLMClient(ProductionLLMClient):
    """Experiment-local client that recreates a broken provider connection.

    This isolated module adds the streaming resilience needed by the
    long-running, fine-grained indicator workbench. Responses are not cached.
    """

    def __init__(self, settings: Any):
        super().__init__(settings)
        # The shared PJLab gateway applies a cluster-level RPM limit.  Reserve
        # staggered request start slots, while allowing already-started streaming
        # generations to overlap.  Serializing the full response stream makes a
        # 41-call project take hours; staggering only starts respects RPM without
        # discarding useful concurrency.
        self._provider_schedule_lock = threading.Lock()
        self._next_provider_request_at = 0.0
        self._provider_min_request_interval = 30.0
        self._response_context = threading.local()

    def chat_text(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_attempts: int = 3,
        use_cache: bool = True,
        timeout: float | None = None,
    ) -> LLMResult:
        return self._chat_text_scheduled(
            system,
            user,
            model=model,
            temperature=temperature,
            max_attempts=max_attempts,
            use_cache=use_cache,
            timeout=timeout,
        )

    def _chat_text_scheduled(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_attempts: int = 3,
        use_cache: bool = True,
        timeout: float | None = None,
    ) -> LLMResult:
        if not self.available:
            return LLMResult(ok=False, error_type="LLMDisabled", error="LLM disabled or no API key.")
        use_model = model or self.settings.glm_model
        last_error = ""
        last_type = ""
        for attempt in range(max_attempts):
            try:
                request: dict[str, Any] = {
                    "model": use_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    # Detailed judgments need room for both reasoning and final
                    # evidence fields. Keep a finite ceiling and reject streams
                    # that report truncation, even if their text parses as JSON.
                    "max_tokens": 16384 if str(use_model).startswith(
                        ("deepseek-v4", "kimi-k3", "glm-5")
                    ) else 4096,
                }
                if timeout is not None:
                    request["timeout"] = timeout
                if (getattr(self._response_context, 'json_object', False)
                        and str(use_model).startswith('deepseek-v4')):
                    request['response_format'] = {'type': 'json_object'}
                # The PJLab-compatible gateway closes long, silent non-streaming
                # requests after roughly 60 seconds.  Consume the provider stream
                # here and reassemble it before JSON parsing so callers retain the
                # same LLMResult contract while the HTTP connection stays active.
                self._wait_for_provider_slot()
                response = self._client_or_new().chat.completions.create(
                    **request,
                    stream=True,
                )
                parts: list[str] = []
                finish_reason = None
                for chunk in response:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    finish_reason = getattr(choices[0], "finish_reason", None) or finish_reason
                    delta = getattr(choices[0], "delta", None)
                    content = getattr(delta, "content", None) if delta is not None else None
                    if content:
                        parts.append(content)
                text = "".join(parts)
                if finish_reason == "length":
                    return LLMResult(
                        ok=False, text=text, model=use_model,
                        error_type="LLMOutputTruncated",
                        error="Provider stopped at the output token limit; incomplete judgment rejected.",
                    )
                return LLMResult(ok=True, text=text, model=use_model)
            except Exception as exc:  # provider exposes multiple exception types
                last_error = str(exc)[:500]
                last_type = type(exc).__name__
                self._client = None
                if attempt < max_attempts - 1:
                    time.sleep(_provider_retry_delay(last_type, last_error, attempt))
        return LLMResult(ok=False, model=use_model, error_type=last_type, error=last_error)

    def _wait_for_provider_slot(self) -> None:
        with self._provider_schedule_lock:
            now = time.monotonic()
            scheduled = max(now, self._next_provider_request_at)
            self._next_provider_request_at = scheduled + self._provider_min_request_interval
        delay = scheduled - now
        if delay > 0:
            time.sleep(delay)

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_attempts: int = 3,
        expect: str = "object",
        timeout: float | None = None,
    ) -> LLMResult:
        previous_format = getattr(self._response_context, 'json_object', False)
        self._response_context.json_object = expect == 'object'
        try:
            result = self.chat_text(
                system,
                user,
                model=model,
                temperature=temperature,
                max_attempts=max_attempts,
                use_cache=False,
                timeout=timeout,
            )
        finally:
            self._response_context.json_object = previous_format
        if not result.ok:
            return result
        parsed = _extract_json(result.text, expect=expect)
        if parsed is not None:
            return LLMResult(ok=True, data=parsed, text=result.text, model=result.model)
        result = LLMResult(
            ok=False, text=result.text, model=result.model, error_type='InvalidLLMJson',
            error='LLM response did not contain valid JSON.', raw=result.text[:1200],
        )
        if result.ok or result.error_type != "InvalidLLMJson" or not result.text:
            return result
        repaired = _repair_single_extra_closer(result.text, expect)
        if repaired is None:
            repaired = _repair_unescaped_inner_quotes(result.text, expect)
        if repaired is None:
            return result
        repaired_text = json.dumps(repaired, ensure_ascii=False)
        return LLMResult(
            ok=True,
            data=repaired,
            text=repaired_text,
            model=result.model or model or self.settings.glm_model,
            raw=result.text,
        )


def _provider_retry_delay(error_type: str, error: str, attempt: int) -> float:
    """Honor an OpenAI-compatible gateway's retry hint for RPM throttling."""
    if error_type == "RateLimitError" or "429" in error:
        match = re.search(r"[\"']retry_after[\"']\s*:\s*([0-9]+(?:\.[0-9]+)?)", error)
        if match:
            return min(float(match.group(1)) + 1.0, 60.0)
        return min(10.0 * (attempt + 1), 60.0)
    return min(1.5 * (attempt + 1), 10.0)


def _repair_single_extra_closer(text: str, expect: str) -> Any:
    """Repair only one extra closing brace/bracket; never rewrite model content."""
    start_char, end_char = ("[", "]") if expect == "array" else ("{", "}")
    start = text.find(start_char)
    end = text.rfind(end_char)
    if start < 0 or end <= start:
        return None
    candidate = text[start:end + 1]
    for index, char in enumerate(candidate[:-1]):
        if char != end_char:
            continue
        try:
            value = json.loads(candidate[:index] + candidate[index + 1:])
        except json.JSONDecodeError:
            continue
        if (expect == "object" and isinstance(value, dict)) or (expect == "array" and isinstance(value, list)):
            return value
    return None


def _repair_unescaped_inner_quotes(text: str, expect: str) -> Any:
    """Escape only clearly internal bare quotes in an otherwise complete JSON value.

    Chinese long-form model answers sometimes contain prose such as
    ``"结论": "项目目标是"AI驱动"但证据不足"``.  A quote already inside a
    JSON string is a closing delimiter only when the next non-space character is
    a JSON structural delimiter.  Every other bare quote is syntax, not content,
    and can be escaped without changing the returned field or wording.
    """
    start_char, end_char = ("[", "]") if expect == "array" else ("{", "}")
    start = text.find(start_char)
    end = text.rfind(end_char)
    if start < 0 or end <= start:
        return None
    candidate = text[start:end + 1]
    output: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(candidate):
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            output.append(char)
            escaped = True
            continue
        if char != '"':
            output.append(char)
            continue
        if not in_string:
            in_string = True
            output.append(char)
            continue
        lookahead = index + 1
        while lookahead < len(candidate) and candidate[lookahead].isspace():
            lookahead += 1
        next_char = candidate[lookahead] if lookahead < len(candidate) else ""
        if next_char in {",", "}", "]", ":", ""}:
            in_string = False
            output.append(char)
        else:
            output.extend(("\\", char))
    try:
        value = json.loads("".join(output))
    except json.JSONDecodeError:
        return None
    if (expect == "object" and isinstance(value, dict)) or (
        expect == "array" and isinstance(value, list)
    ):
        return value
    return None

__all__ = ["LLMClient", "LLMResult"]
