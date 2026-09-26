"""Shared LLM client for the impact-evaluation pipeline.

Single place that talks to the model provider (yunwu / GLM-compatible OpenAI API).
Replaces the duplicated `OpenAI(...)` + manual JSON slicing that used to live in
`agents/material_analysis.py` and `agents/evaluation.py`.

Design goals:
- One `LLMClient` constructed from `Settings`; agents call `chat_json` / `chat_text`.
- Robust JSON extraction (handles ```json fences, leading prose, arrays or objects).
- Bounded retries with a clear, structured failure result — never raise into the
  scoring path; callers decide how to degrade.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import Settings


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass
class LLMResult:
    ok: bool
    data: Any = None            # parsed JSON (dict/list) when ok and JSON requested
    text: str = ""             # raw text content
    model: str = ""
    error_type: str = ""
    error: str = ""
    raw: str = ""              # raw content on parse failure (truncated)


class LLMClient:
    """Thin wrapper over the OpenAI-compatible chat API used across agents."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        return bool(self.settings.use_llm and self.settings.has_real_api_key)

    def _client_or_new(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.glm_api_key,
                base_url=self.settings.glm_base_url,
                timeout=self.settings.llm_timeout,
                max_retries=0,  # we do our own retry loop below
            )
        return self._client

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
                }
                if timeout is not None:
                    request["timeout"] = timeout
                response = self._client_or_new().chat.completions.create(
                    **request,
                )
                text = response.choices[0].message.content or ""
                return LLMResult(ok=True, text=text, model=use_model)
            except Exception as exc:  # noqa: BLE001 - provider raises many types
                last_error = str(exc)[:500]
                last_type = type(exc).__name__
                if attempt < max_attempts - 1:
                    time.sleep(1.5 * (attempt + 1))
        return LLMResult(ok=False, model=use_model, error_type=last_type, error=last_error)





    def vision_text(
        self,
        prompt: str,
        image_png: bytes,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_attempts: int = 3,
        detail: str = "high",
    ) -> LLMResult:
        """多模态读图：把一张 PNG 交给视觉模型，返回其读出的文本。"""
        if not self.available:
            return LLMResult(ok=False, error_type="LLMDisabled", error="LLM disabled or no API key.")
        use_model = model or self.settings.vision_model
        b64 = base64.b64encode(image_png).decode()
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": detail},
            },
        ]
        last_error = ""
        last_type = ""
        for attempt in range(max_attempts):
            try:
                response = self._client_or_new().chat.completions.create(
                    model=use_model,
                    messages=[{"role": "user", "content": content}],
                    temperature=temperature,
                )
                text = response.choices[0].message.content or ""
                return LLMResult(ok=True, text=text, model=use_model)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)[:500]
                last_type = type(exc).__name__
                if attempt < max_attempts - 1:
                    time.sleep(1.5 * (attempt + 1))
        return LLMResult(ok=False, model=use_model, error_type=last_type, error=last_error)

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_attempts: int = 3,
        expect: str = "object",  # "object" or "array"
        timeout: float | None = None,
    ) -> LLMResult:
        use_model = model or self.settings.glm_model
        cache_system = f"{system}\n[expected-json:{expect}]"
        cache_key = self._cache_key(use_model, cache_system, user, temperature)
        cached = self._load_cache(cache_key)
        if cached is not None:
            parsed = _extract_json(cached, expect=expect)
            if parsed is not None:
                return LLMResult(ok=True, data=parsed, text=cached, model=use_model)
        result = self.chat_text(
            system,
            user,
            model=model,
            temperature=temperature,
            max_attempts=max_attempts,
            use_cache=False,
            timeout=timeout,
        )
        if not result.ok:
            return result
        parsed = _extract_json(result.text, expect=expect)
        if parsed is None:
            return LLMResult(
                ok=False,
                model=result.model,
                text=result.text,
                error_type="InvalidLLMJson",
                error="LLM response did not contain valid JSON.",
                raw=result.text[:1200],
            )
        self._save_cache(cache_key, result.model, result.text)
        return LLMResult(ok=True, data=parsed, text=result.text, model=result.model)


def _extract_json(text: str, expect: str = "object") -> Any:
    """Best-effort JSON extraction from a model response.

    Tries, in order: fenced ```json blocks, then the widest object/array slice.
    """
    if not text:
        return None
    candidates: list[str] = []
    for match in _FENCE_RE.findall(text):
        candidates.append(match.strip())
    candidates.append(text)

    open_ch, close_ch = ("[", "]") if expect == "array" else ("{", "}")
    for candidate in candidates:
        # direct parse
        try:
            return json.loads(candidate)
        except Exception:
            pass
        start = candidate.find(open_ch)
        end = candidate.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except Exception:
                continue
    return None
