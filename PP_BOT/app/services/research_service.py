"""Research service for PP_BOT.

This layer normalizes source hints, extracts text from local files and URLs
when available, and produces a citation-backed research result that other
agents can consume.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import httpx

from app.config import SOURCE_DIR, settings
from app.models import AttachedFile, ResearchHit, ResearchRequest, ResearchResult, SourceDocument, SourceType
from app.prompts import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_TEMPLATE
from app.services.ai_service import ai_service
from app.services.microsoft_auth_service import get_access_token


@dataclass
class _CandidateDocument:
    document: SourceDocument
    score: float


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _truncate(text: str, limit: int = 700) -> str:
    text = _normalize_whitespace(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return _normalize_whitespace(text)


def _guess_source_type(source_hint: str, fallback: Optional[SourceType]) -> SourceType:
    hint = (source_hint or "").strip().lower()
    if hint.startswith("http://") or hint.startswith("https://"):
        return fallback or SourceType.web
    if hint.endswith(".md") or hint.endswith(".txt") or hint.endswith(".json") or hint.endswith(".csv"):
        return fallback or SourceType.file
    return fallback or SourceType.text


def _safe_title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title() or path.name


class ResearchService:
    """Ingests source hints and returns a grounded research result."""

    def _sharepoint_graph_site_url(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        if "sharepoint.com" not in (parsed.netloc or "").lower():
            return None
        site_path = parsed.path.rstrip("/")
        if not site_path:
            return None
        encoded_path = quote(site_path, safe="/")
        return f"https://graph.microsoft.com/v1.0/sites/{parsed.netloc}:{encoded_path}"

    def _wiki_headers(self) -> Dict[str, str]:
        token = (settings.WIKI_BEARER_TOKEN or "").strip()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _is_confluence_login_page(self, response: httpx.Response) -> bool:
        final_url = str(response.url).lower()
        if "login.action" in final_url:
            return True
        body = (response.text or "").lower()
        return "log in - confluence" in body or "permissionviolation=true" in final_url

    async def _read_sharepoint_url(self, url: str) -> str:
        token = get_access_token()
        if not token:
            return ""
        graph_url = self._sharepoint_graph_site_url(url)
        if not graph_url:
            return ""

        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, trust_env=True) as client:
                site_response = await client.get(graph_url, headers=headers)
                if site_response.status_code >= 400:
                    return ""
                site_payload = site_response.json()
                lines = [
                    f"SharePoint site: {site_payload.get('displayName') or site_payload.get('name') or url}",
                    f"Site URL: {site_payload.get('webUrl') or url}",
                ]

                pages_url = f"{graph_url}/pages/microsoft.graph.sitePage?$top=10"
                pages_response = await client.get(pages_url, headers=headers)
                if pages_response.status_code < 400:
                    pages_payload = pages_response.json()
                    for page in pages_payload.get("value", []):
                        title = page.get("title") or page.get("name") or "Untitled page"
                        web_url = page.get("webUrl") or ""
                        description = page.get("description") or ""
                        lines.append(f"Page: {title}")
                        if description:
                            lines.append(f"Description: {description}")
                        if web_url:
                            lines.append(f"Page URL: {web_url}")

                drives_url = f"{graph_url}/drives?$top=10"
                drives_response = await client.get(drives_url, headers=headers)
                if drives_response.status_code < 400:
                    drives_payload = drives_response.json()
                    for drive in drives_payload.get("value", []):
                        drive_name = drive.get("name") or "Document library"
                        web_url = drive.get("webUrl") or ""
                        lines.append(f"Library: {drive_name}")
                        if web_url:
                            lines.append(f"Library URL: {web_url}")

                return _normalize_whitespace("\n".join(lines))
        except Exception:
            return ""

    async def _read_wiki_url(self, url: str) -> str:
        headers = self._wiki_headers()
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, trust_env=True) as client:
                response = await client.get(url, headers=headers)
                if response.status_code >= 400 or self._is_confluence_login_page(response):
                    return ""
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    return _strip_html(response.text)
                return _normalize_whitespace(response.text)
        except Exception:
            return ""

    async def _read_url(self, url: str) -> str:
        lower = url.lower()
        if "sharepoint.com" in lower:
            sharepoint_content = await self._read_sharepoint_url(url)
            if sharepoint_content:
                return sharepoint_content
        if "wiki.rjf.com" in lower or "confluence" in lower:
            wiki_content = await self._read_wiki_url(url)
            if wiki_content:
                return wiki_content
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, trust_env=True) as client:
                response = await client.get(url)
                if response.status_code >= 400:
                    return ""
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    return _strip_html(response.text)
                return _normalize_whitespace(response.text)
        except Exception:
            return ""

    def _read_local_file(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        if path.suffix.lower() in {".json"}:
            try:
                return json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2)
            except Exception:
                return _normalize_whitespace(path.read_text(encoding="utf-8", errors="ignore"))
        return _normalize_whitespace(path.read_text(encoding="utf-8", errors="ignore"))

    def _resolve_local_path(self, hint: str) -> Optional[Path]:
        value = (hint or "").strip()
        if not value:
            return None
        candidate = Path(value).expanduser()
        if candidate.exists():
            return candidate
        source_candidate = SOURCE_DIR / value
        if source_candidate.exists():
            return source_candidate
        cwd_candidate = Path.cwd() / value
        if cwd_candidate.exists():
            return cwd_candidate
        return None

    def _is_supported_local_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in {
            ".txt",
            ".md",
            ".rst",
            ".json",
            ".csv",
            ".tsv",
            ".log",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".htm",
            ".py",
            ".sql",
        }

    def _document_from_attachment(self, attachment: AttachedFile) -> Optional[SourceDocument]:
        content = _normalize_whitespace(attachment.content)
        if not content:
            return None
        title = Path(attachment.name).stem.replace("_", " ").replace("-", " ").title() or attachment.name
        source_id = re.sub(r"[^a-zA-Z0-9]+", "-", attachment.name).strip("-").lower() or "attachment"
        return SourceDocument(
            source_id=source_id,
            title=title,
            url=None,
            source_type=SourceType.file,
            content=content,
            excerpt=_truncate(content, 240),
            metadata={
                "origin": "attachment",
                "name": attachment.name,
                "mime_type": attachment.mime_type,
            },
        )

    def _load_directory_documents(self, directory_hint: str) -> List[SourceDocument]:
        directory = self._resolve_local_path(directory_hint)
        if directory is None or not directory.exists() or not directory.is_dir():
            return []

        documents: List[SourceDocument] = []
        for file_path in sorted(directory.rglob("*")):
            if not self._is_supported_local_file(file_path):
                continue
            content = self._read_local_file(file_path)
            if not content:
                continue
            source_id = re.sub(r"[^a-zA-Z0-9]+", "-", str(file_path.relative_to(directory))).strip("-").lower() or "file"
            documents.append(
                SourceDocument(
                    source_id=source_id,
                    title=_safe_title_from_path(file_path),
                    url=None,
                    source_type=SourceType.file,
                    content=content,
                    excerpt=_truncate(content, 240),
                    metadata={
                        "origin": "directory-file",
                        "directory": str(directory),
                        "path": str(file_path),
                    },
                )
            )
        return documents

    async def _load_document(self, source_hint: str, source_type: Optional[SourceType]) -> Optional[SourceDocument]:
        hint = (source_hint or "").strip()
        if not hint:
            return None

        doc_type = _guess_source_type(hint, source_type)
        title = hint
        url: Optional[str] = None
        content = ""
        metadata: Dict[str, Any] = {}

        if hint.startswith("http://") or hint.startswith("https://"):
            url = hint
            parsed = urlparse(hint)
            title = parsed.path.rsplit("/", 1)[-1] or parsed.netloc
            content = await self._read_url(hint)
            metadata["origin"] = "url"
        else:
            local_path = Path(hint)
            if not local_path.is_absolute():
                candidate = SOURCE_DIR / hint
                if candidate.exists():
                    local_path = candidate
            if local_path.exists():
                title = _safe_title_from_path(local_path)
                content = self._read_local_file(local_path)
                metadata["origin"] = "file"
                metadata["path"] = str(local_path)
            else:
                title = hint[:80]
                content = hint
                metadata["origin"] = "text"

        if not content:
            return None

        excerpt = _truncate(content, 240)
        source_id = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower() or "source"
        return SourceDocument(
            source_id=source_id,
            title=title,
            url=url,
            source_type=doc_type,
            content=content,
            excerpt=excerpt,
            metadata=metadata,
        )

    def _score_document(self, topic: str, document: SourceDocument) -> float:
        topic_words = {word for word in re.findall(r"[a-z0-9]+", topic.lower()) if len(word) > 2}
        content_words = set(re.findall(r"[a-z0-9]+", document.content.lower()))
        title_words = set(re.findall(r"[a-z0-9]+", document.title.lower()))
        overlap = len(topic_words.intersection(content_words.union(title_words)))
        recency_bonus = 0.0
        if "last_modified" in document.metadata:
            recency_bonus = 0.2
        return float(overlap) + recency_bonus

    def _summarize_hits(self, documents: List[SourceDocument], scored: List[_CandidateDocument]) -> List[str]:
        findings: List[str] = []
        for candidate in scored:
            document = candidate.document
            findings.append(
                f"{document.title}: {_truncate(document.excerpt or document.content, 180)}"
            )
        return findings[:5]

    async def run(self, request: ResearchRequest) -> ResearchResult:
        candidates: List[SourceDocument] = []

        for source_hint in request.sources:
            document = await self._load_document(source_hint, request.source_type)
            if document is not None:
                candidates.append(document)

        for local_directory in request.local_directories:
            candidates.extend(self._load_directory_documents(local_directory))

        for attachment in request.attached_files:
            document = self._document_from_attachment(attachment)
            if document is not None:
                candidates.append(document)

        if not candidates and request.topic.strip():
            candidates.append(
                SourceDocument(
                    source_id="topic-only",
                    title=request.topic.strip(),
                    url=None,
                    source_type=request.source_type or SourceType.text,
                    content=request.topic.strip(),
                    excerpt=_truncate(request.topic, 240),
                    metadata={"origin": "topic"},
                )
            )

        scored = [
            _CandidateDocument(document=document, score=self._score_document(request.topic, document))
            for document in candidates
        ]
        scored.sort(key=lambda item: item.score, reverse=True)

        top_documents = [item.document for item in scored[: request.max_results]]
        citations = [
            ResearchHit(
                source_id=document.source_id,
                title=document.title,
                url=document.url,
                source_type=document.source_type,
                score=next((item.score for item in scored if item.document.source_id == document.source_id), 0.0),
                excerpt=document.excerpt,
                metadata=document.metadata,
            )
            for document in top_documents
        ]

        research_context = {
            "topic": request.topic,
            "sources": [
                {
                    "source_id": doc.source_id,
                    "title": doc.title,
                    "url": doc.url,
                    "source_type": doc.source_type.value,
                    "excerpt": doc.excerpt,
                    "metadata": doc.metadata,
                    "content": _truncate(doc.content, 1200),
                }
                for doc in top_documents
            ],
        }

        user_prompt = RESEARCH_USER_TEMPLATE.format(
            topic=request.topic,
            sources=", ".join(request.sources) if request.sources else "None provided",
            source_type=request.source_type.value if request.source_type else "auto",
            max_results=request.max_results,
        )

        model_payload = await ai_service.async_generate_json(
            RESEARCH_SYSTEM_PROMPT,
            json.dumps({"request": user_prompt, "context": research_context}, indent=2),
            temperature=0.2,
            max_tokens=1200,
        )

        summary = str(model_payload.get("summary") or "").strip()
        if not summary:
            summary = (
                f"Research collected {len(top_documents)} source(s) related to '{request.topic}'. "
                f"The strongest evidence emphasizes {top_documents[0].title if top_documents else 'the topic'}."
            )

        findings = model_payload.get("findings")
        if not isinstance(findings, list) or not findings:
            findings = self._summarize_hits(top_documents, scored)

        risks = model_payload.get("risks")
        if not isinstance(risks, list) or not risks:
            risks = [
                "Source coverage may be incomplete if the wiki or SharePoint content is not accessible.",
                "Some inputs may be plain text hints rather than fully indexed documents.",
            ]

        assumptions = model_payload.get("assumptions")
        if not isinstance(assumptions, list) or not assumptions:
            assumptions = [
                "Provided source hints are representative of the relevant knowledge base.",
                "The source text extracted from files or URLs is sufficient for synthesis.",
            ]

        open_questions = model_payload.get("open_questions")
        if not isinstance(open_questions, list) or not open_questions:
            open_questions = [
                "Which wiki pages and SharePoint libraries are authoritative for this topic?",
                "Are there additional source systems that should be included in the index?",
            ]

        raw_context = None
        if request.include_raw_context:
            raw_context = json.dumps(research_context, indent=2)

        return ResearchResult(
            topic=request.topic,
            summary=summary,
            findings=[str(item) for item in findings],
            risks=[str(item) for item in risks],
            assumptions=[str(item) for item in assumptions],
            open_questions=[str(item) for item in open_questions],
            citations=citations,
            raw_context=raw_context,
        )


research_service = ResearchService()
