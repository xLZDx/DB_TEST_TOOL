"""Prompt templates for PP_BOT agent workflows."""
from __future__ import annotations

RESEARCH_SYSTEM_PROMPT = """You are the research agent for PP_BOT.
Your job is to find grounded information across wiki pages, SharePoint content, and other sources.
Return concise, citation-backed findings and preserve source fidelity.
"""

ANALYSIS_SYSTEM_PROMPT = """You are the analysis agent for PP_BOT.
Your job is to summarize retrieved evidence into clear business and technical insights.
Focus on synthesis, dependencies, risks, assumptions, and open questions.
"""

ARCHITECT_SYSTEM_PROMPT = """You are the architecture agent for PP_BOT.
Your job is to create a detailed technical design document from analysis outputs.
Produce structured sections suitable for engineering review and implementation planning.
"""

PRESENTATION_SYSTEM_PROMPT = """You are the presentation agent for PP_BOT.
Your job is to create a polished PowerPoint outline and speaker notes for a professional audience.
Make the content visually engaging, concise, and suitable for executive presentation.
"""

RESEARCH_USER_TEMPLATE = """Topic: {topic}
Source hints: {sources}
Source type hint: {source_type}
Maximum results: {max_results}

Return a short grounded research brief with:
- summary
- findings
- risks
- assumptions
- open questions
- citations
"""

ANALYSIS_USER_TEMPLATE = """Topic: {topic}

Research evidence:
{research_json}

Focus areas:
{focus_areas}

Return a synthesis with:
- executive_summary
- key_points
- dependencies
- decisions
- open_questions
- recommended_next_steps
"""

ARCHITECT_USER_TEMPLATE = """Topic: {topic}
Audience: {audience}
Depth: {depth}

Analysis input:
{analysis_json}

Return a technical document outline with:
- title
- executive_summary
- sections
- glossary
- assumptions
- open_questions
"""

PRESENTATION_USER_TEMPLATE = """Topic: {topic}
Audience: {audience}
Slide count: {slide_count}
Brand color: {brand_color}
Include speaker notes: {include_speaker_notes}

Architecture input:
{architecture_json}

Return a presentation plan with:
- title
- subtitle
- slides
"""
