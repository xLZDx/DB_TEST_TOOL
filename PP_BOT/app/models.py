"""Shared data models for PP_BOT."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    wiki = "wiki"
    sharepoint = "sharepoint"
    web = "web"
    file = "file"
    text = "text"


class AgentRole(str, Enum):
    researcher = "researcher"
    analyst = "analyst"
    architect = "architect"
    presenter = "presenter"


class SourceDocument(BaseModel):
    source_id: str = Field(..., description="Stable identifier for the source document")
    title: str = Field(..., description="Document title")
    url: Optional[str] = Field(default=None, description="Canonical URL if available")
    source_type: SourceType = Field(..., description="Type of source")
    content: str = Field(..., description="Extracted text content")
    excerpt: Optional[str] = Field(default=None, description="Short relevant excerpt")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional source metadata")


class AttachedFile(BaseModel):
    name: str = Field(..., description="Original file name")
    content: str = Field(..., description="Text extracted from the uploaded file")
    mime_type: Optional[str] = Field(default=None, description="Detected file MIME type")


class SearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Topic or question to investigate")
    sources: List[str] = Field(default_factory=list, description="Candidate source URLs, file paths, or IDs")
    source_type: Optional[SourceType] = Field(default=None, description="Optional source type hint")
    max_results: int = Field(default=5, ge=1, le=25)


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Topic to research")
    sources: List[str] = Field(default_factory=list, description="URLs, wiki pages, SharePoint locations, or text IDs")
    local_directories: List[str] = Field(default_factory=list, description="Local directories to search recursively for supporting files")
    attached_files: List[AttachedFile] = Field(default_factory=list, description="Text files uploaded from the GUI to include in the analysis")
    source_type: Optional[SourceType] = Field(default=None, description="Optional source type hint")
    max_results: int = Field(default=5, ge=1, le=25)
    include_raw_context: bool = Field(default=False, description="Include trimmed source text in the response")


class ResearchHit(BaseModel):
    source_id: str
    title: str
    url: Optional[str] = None
    source_type: SourceType
    score: float = 0.0
    excerpt: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchResult(BaseModel):
    topic: str
    summary: str
    findings: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    citations: List[ResearchHit] = Field(default_factory=list)
    raw_context: Optional[str] = None


class AnalysisRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    research: ResearchResult
    focus_areas: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    topic: str
    executive_summary: str
    key_points: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)


class ArchitectureRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    analysis: AnalysisResult
    audience: str = Field(default="engineering")
    depth: str = Field(default="detailed", description="e.g. overview, detailed, implementation")


class ArchitectureSection(BaseModel):
    heading: str
    body: str
    bullets: List[str] = Field(default_factory=list)


class ArchitectureResult(BaseModel):
    topic: str
    title: str
    executive_summary: str
    sections: List[ArchitectureSection] = Field(default_factory=list)
    glossary: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class PresentationRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    architecture: ArchitectureResult
    audience: str = Field(default="stakeholders")
    slide_count: int = Field(default=8, ge=4, le=20)
    brand_color: str = Field(default="#1F4E79")
    include_speaker_notes: bool = Field(default=True)


class PresentationSlide(BaseModel):
    title: str
    subtitle: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    image_prompts: List[str] = Field(default_factory=list)


class PresentationResult(BaseModel):
    topic: str
    title: str
    subtitle: Optional[str] = None
    slides: List[PresentationSlide] = Field(default_factory=list)
    output_path: Optional[str] = None


class AgentRunResponse(BaseModel):
    ok: bool = True
    role: AgentRole
    topic: str
    result: Dict[str, Any]
