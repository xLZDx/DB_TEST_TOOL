"""Analysis service for PP_BOT.

Consumes research output and produces a concise synthesis that downstream
architecture and presentation layers can reuse.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.models import AnalysisRequest, AnalysisResult
from app.prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_TEMPLATE
from app.services.ai_service import ai_service


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _merge_lists(*values: Any) -> List[str]:
    items: List[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _as_list(value):
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items


class AnalysisService:
    """Transforms research evidence into analysis-ready outputs."""

    def _local_result(self, request: AnalysisRequest) -> AnalysisResult:
        research = request.research
        key_points = _merge_lists(
            research.findings,
            request.focus_areas,
        ) or [research.summary]

        dependencies = _merge_lists(
            research.assumptions,
            research.risks,
        )
        decisions = _merge_lists(
            [f"Validate {area}" for area in request.focus_areas],
            research.findings[:2],
        )
        recommended_next_steps = _merge_lists(
            research.open_questions,
            ["Confirm source ownership", "Validate integration constraints", "Draft implementation sequence"],
        )

        return AnalysisResult(
            topic=request.topic,
            executive_summary=research.summary,
            key_points=key_points,
            dependencies=dependencies,
            decisions=decisions,
            open_questions=_merge_lists(research.open_questions),
            recommended_next_steps=recommended_next_steps,
        )

    def _coerce_result(self, request: AnalysisRequest, payload: Dict[str, Any]) -> AnalysisResult:
        if not payload or "text" in payload:
            return self._local_result(request)

        executive_summary = str(
            payload.get("executive_summary")
            or payload.get("summary")
            or request.research.summary
        ).strip()

        return AnalysisResult(
            topic=request.topic,
            executive_summary=executive_summary or request.research.summary,
            key_points=_merge_lists(payload.get("key_points"), request.research.findings),
            dependencies=_merge_lists(payload.get("dependencies"), request.research.assumptions, request.research.risks),
            decisions=_merge_lists(payload.get("decisions")),
            open_questions=_merge_lists(payload.get("open_questions"), request.research.open_questions),
            recommended_next_steps=_merge_lists(
                payload.get("recommended_next_steps"),
                ["Confirm scope", "Refine design", "Prepare implementation plan"],
            ),
        )

    async def run(self, request: AnalysisRequest) -> AnalysisResult:
        research_json = json.dumps(request.research.model_dump(), indent=2, ensure_ascii=False)
        user_prompt = ANALYSIS_USER_TEMPLATE.format(
            topic=request.topic,
            research_json=research_json,
            focus_areas=", ".join(request.focus_areas) if request.focus_areas else "None",
        )

        payload = await ai_service.async_generate_json(
            ANALYSIS_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.2,
            max_tokens=1400,
        )
        return self._coerce_result(request, payload)


analysis_service = AnalysisService()
