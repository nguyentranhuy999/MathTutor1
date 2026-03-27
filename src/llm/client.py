"""Shared LLM client utilities for structured JSON generation."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

import requests
from dotenv import load_dotenv


class LLMClient(Protocol):
    def generate_json(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        ...


class LLMGenerationError(RuntimeError):
    """Raised when the configured LLM cannot return valid JSON output."""


class OpenRouterLLMClient:
    """OpenRouter-backed JSON generation client."""

    def __init__(
        self,
        api_key: str,
        model_id: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: int = 45,
        app_name: str = "problem-formalizer",
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.app_name = app_name

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise LLMGenerationError("LLM returned empty content")

        fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced_match:
            text = fenced_match.group(1).strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text.strip("`").strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            object_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if not object_match:
                raise LLMGenerationError("LLM response did not contain a valid JSON object") from None
            parsed = json.loads(object_match.group(1))

        if not isinstance(parsed, dict):
            raise LLMGenerationError("LLM JSON response must be an object")
        return parsed

    def generate_json(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": self.app_name,
        }
        payload = {
            "model": self.model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMGenerationError(f"{task_name} request failed: {exc}") from exc

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMGenerationError(f"{task_name} response shape was invalid") from exc

        return self._parse_json_content(content)


def build_default_llm_client() -> LLMClient | None:
    """Build the default OpenRouter client from environment variables if available."""
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model_id = os.getenv("OPENROUTER_MODEL_ID", "qwen/qwen-2.5-7b-instruct")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    timeout_seconds = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "45"))
    app_name = os.getenv("OPENROUTER_APP_NAME", "problem-formalizer")

    if not api_key:
        return None

    return OpenRouterLLMClient(
        api_key=api_key,
        model_id=model_id,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        app_name=app_name,
    )

