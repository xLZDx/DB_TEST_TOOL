"""AI provider adapter for PP_BOT.

Supports GitHub Copilot-compatible and OpenAI-compatible endpoints, with a
deterministic local fallback so the app can run without secrets configured.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI

from app.config import settings


_RUNTIME_AI_CONFIG: Dict[str, str] = {}


@dataclass
class AIResponse:
    text: str
    raw: Optional[Any] = None


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def set_runtime_ai_config(
    *,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, str]:
    """Store temporary runtime AI settings without touching environment variables."""
    updates = {
        "provider": (provider or "").strip(),
        "api_key": (api_key or "").strip(),
        "base_url": (base_url or "").strip(),
        "model": (model or "").strip(),
    }
    for key, value in updates.items():
        if value:
            _RUNTIME_AI_CONFIG[key] = value
        elif key in _RUNTIME_AI_CONFIG:
            del _RUNTIME_AI_CONFIG[key]
    return dict(_RUNTIME_AI_CONFIG)


def clear_runtime_ai_config() -> None:
    """Clear any temporary runtime AI settings."""
    _RUNTIME_AI_CONFIG.clear()


def get_runtime_ai_config() -> Dict[str, str]:
    return dict(_RUNTIME_AI_CONFIG)


class AIService:
    """Small wrapper around an OpenAI-compatible chat endpoint."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def _runtime_value(self, key: str) -> str:
        return _RUNTIME_AI_CONFIG.get(key, "").strip()

    def _resolve_provider(self) -> str:
        runtime_provider = self._runtime_value("provider")
        if runtime_provider:
            return runtime_provider.lower()
        return settings.AI_PROVIDER.strip().lower()

    def _resolve_api_key(self) -> str:
        runtime_api_key = self._runtime_value("api_key")
        if runtime_api_key:
            return runtime_api_key

        provider = self._resolve_provider()
        if provider == "openai":
            return settings.OPENAI_API_KEY.strip()
        return settings.GITHUBCOPILOT_API_KEY.strip() or settings.OPENAI_API_KEY.strip()

    def _resolve_base_url(self) -> str:
        runtime_base_url = self._runtime_value("base_url")
        if runtime_base_url:
            return runtime_base_url

        provider = self._resolve_provider()
        if provider == "openai":
            return settings.OPENAI_BASE_URL.strip()
        return settings.GITHUBCOPILOT_BASE_URL.strip() or settings.OPENAI_BASE_URL.strip()

    def _resolve_model(self) -> str:
        runtime_model = self._runtime_value("model")
        if runtime_model:
            return runtime_model

        if settings.AI_MODEL.strip():
            return settings.AI_MODEL.strip()

        provider = self._resolve_provider()
        if provider == "openai":
            return settings.OPENAI_MODEL.strip()
        return settings.GITHUBCOPILOT_MODEL.strip() or settings.OPENAI_MODEL.strip()

    def _build_client(self) -> Optional[OpenAI]:
        api_key = self._resolve_api_key()
        if not api_key:
            return None

        if self._client is not None:
            return self._client

        kwargs: Dict[str, Any] = {"api_key": api_key}
        base_url = self._resolve_base_url()
        if base_url:
            kwargs["base_url"] = base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def is_configured(self) -> bool:
        return bool(self._resolve_api_key())

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self._resolve_provider(),
            "model": self._resolve_model(),
            "base_url": self._resolve_base_url(),
            "configured": self.is_configured(),
            "runtime_override": bool(_RUNTIME_AI_CONFIG),
            "mode": "live" if self.is_configured() and self._resolve_model() else "fallback",
            "has_api_key": bool(self._resolve_api_key()),
        }

    def test_connection(self) -> Dict[str, Any]:
        model = self._resolve_model()
        if not self.is_configured() or not model:
            return {
                "ok": False,
                "connected": False,
                "mode": "fallback",
                "message": "No AI credentials configured. The app will use the deterministic local fallback until you connect.",
                "status": self.status(),
            }

        try:
            probe = self.generate_text(
                "You are a connectivity tester. Reply with the single word OK.",
                "Confirm that the model is reachable.",
                temperature=0.0,
                max_tokens=16,
            )
            return {
                "ok": True,
                "connected": True,
                "mode": "live",
                "message": "AI provider is reachable.",
                "probe": probe[:120],
                "status": self.status(),
            }
        except Exception as exc:  # pragma: no cover - network/provider specific
            return {
                "ok": False,
                "connected": False,
                "mode": "live",
                "message": str(exc),
                "status": self.status(),
            }

    def _local_summary(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"{system_prompt}\n{user_prompt}".strip()
        lowered = prompt.lower()

        if "presentation" in lowered or "slide" in lowered:
            return (
                "Title: Executive briefing\n"
                "Summary: This topic requires a stakeholder-friendly presentation "
                "with clear problem statement, architecture overview, key risks, "
                "implementation phases, and next steps."
            )

        if "architecture" in lowered or "design" in lowered:
            return (
                "Title: Technical architecture\n"
                "Summary: The solution should centralize source ingestion, preserve "
                "citations, separate research from synthesis, and generate reusable "
                "deliverables for analysis, design, and presentation."
            )

        if "research" in lowered or "find" in lowered or "evidence" in lowered:
            return (
                "Summary: Relevant sources should be collected from wiki and "
                "SharePoint content, normalized into searchable documents, and "
                "ranked by topical overlap and recency."
            )

        return (
            "Summary: The request should be handled with structured inputs, "
            "traceable outputs, and a fallback path when model access is not available."
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        client = self._build_client()
        model = self._resolve_model()

        if client is None or not model:
            return self._local_summary(system_prompt, user_prompt)

        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> Dict[str, Any]:
        text = self.generate_text(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            return json.loads(_strip_json_fences(text))
        except json.JSONDecodeError:
            return {"text": text}

    async def async_generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        return await asyncio.to_thread(
            self.generate_text,
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def async_generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self.generate_json,
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )


ai_service = AIService()
