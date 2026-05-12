"""Architecture service for PP_BOT.

Consumes analysis output and produces a detailed technical document structure
that can be rendered as markdown, JSON, or reused by the presentation layer.
"""
from __future__ import annotations

from typing import List

from ..models import ArchitectureRequest, ArchitectureResult, ArchitectureSection
from ..prompts import ARCHITECT_SYSTEM_PROMPT


def _compact_list(items: List[str]) -> List[str]:
    compacted: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        compacted.append(text)
    return compacted


class ArchitectureService:
    """Builds architecture artifacts from analysis outputs."""

    def _local_result(self, request: ArchitectureRequest) -> ArchitectureResult:
        analysis = request.analysis
        title = f"{request.topic} - Technical Architecture"

        sections = [
            ArchitectureSection(
                heading="1. Executive Summary",
                body=analysis.executive_summary,
                bullets=_compact_list(analysis.key_points[:5]),
            ),
            ArchitectureSection(
                heading="2. Business and Technical Drivers",
                body=(
                    "This solution should support the current processing flow while "
                    "preserving traceability across transactions, positions, and balances."
                ),
                bullets=_compact_list(
                    analysis.dependencies[:4] + analysis.decisions[:2]
                ),
            ),
            ArchitectureSection(
                heading="3. Proposed Design",
                body=(
                    "Use a modular pipeline: source ingestion, normalization, research "
                    "evidence, analysis synthesis, architecture drafting, and presentation "
                    "generation. Each stage should produce machine-readable output for reuse."
                ),
                bullets=[
                    "Separate source ingestion from synthesis",
                    "Track citations and provenance",
                    "Preserve raw source context for auditability",
                    "Support both human-readable and JSON outputs",
                ],
            ),
            ArchitectureSection(
                heading="4. Integration Considerations",
                body=(
                    "Integration points should cover wiki content, SharePoint content, "
                    "document storage, and PowerPoint export. The workflow should remain "
                    "extendable to additional repositories later."
                ),
                bullets=_compact_list(
                    analysis.recommended_next_steps[:4] + analysis.open_questions[:3]
                ),
            ),
            ArchitectureSection(
                heading="5. Delivery and Risks",
                body=(
                    "Delivery should prioritize a working MVP with local deterministic "
                    "outputs, then layer in richer AI-assisted synthesis and source connectors."
                ),
                bullets=[
                    "Unclear source quality may affect summary accuracy",
                    "SharePoint permissions may restrict retrieval",
                    "Presentation generation may require manual image selection",
                ],
            ),
        ]

        glossary = _compact_list(
            [
                "Source provenance: the origin and traceability of a fact",
                "Research hit: a ranked source snippet used to support findings",
                "Analysis result: the synthesized interpretation of research evidence",
                "Architecture result: the detailed technical structure derived from analysis",
            ]
        )

        assumptions = _compact_list(
            analysis.decisions[:2]
            + [
                "Source connectors can be expanded incrementally",
                "The initial MVP can operate with local fallback logic",
            ]
        )

        open_questions = _compact_list(
            analysis.open_questions
            + [
                "Which wiki platform and SharePoint APIs should be integrated first?",
                "Should decks be branded per business unit or use one corporate theme?",
            ]
        )

        return ArchitectureResult(
            topic=request.topic,
            title=title,
            executive_summary=analysis.executive_summary,
            sections=sections,
            glossary=glossary,
            assumptions=assumptions,
            open_questions=open_questions,
        )

    def generate(self, request: ArchitectureRequest) -> ArchitectureResult:
        # Deterministic local output for now; AI layer can be added later without
        # changing the API contract.
        return self._local_result(request)

    async def async_generate(self, request: ArchitectureRequest) -> ArchitectureResult:
        return self.generate(request)


architecture_service = ArchitectureService()
