"""AI Service for IntelliTest.

Provides multi-provider AI completion using the same GitHub Copilot integration
as db-testing-tool, portable as a standalone module.
"""
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_model() -> str:
    provider = (settings.AI_PROVIDER or "openai").lower()
    if provider == "githubcopilot":
        return (settings.GITHUBCOPILOT_MODEL or "gpt-4o").strip()
    return settings.AI_MODEL or settings.OPENAI_MODEL or "gpt-4o"


def _is_model_not_supported(exc: Exception) -> bool:
    text = str(exc).lower()
    return "model_not_supported" in text or "requested model is not supported" in text


def _get_client():
    """Build an OpenAI SDK client for the configured provider."""
    provider = (settings.AI_PROVIDER or "openai").lower()
    verify = settings.OPENAI_VERIFY_SSL
    ca = settings.OPENAI_CA_BUNDLE
    if ca:
        verify = ca

    if provider == "githubcopilot":
        github_verify = settings.GITHUB_VERIFY_SSL
        if settings.GITHUB_CA_BUNDLE:
            github_verify = settings.GITHUB_CA_BUNDLE
        elif not verify:
            github_verify = False
        http_client = httpx.Client(verify=github_verify,
                                   timeout=float(settings.AI_HTTP_TIMEOUT_SECONDS),
                                   trust_env=True)
        from openai import OpenAI
        from app.services.copilot_auth import get_copilot_token
        token = get_copilot_token()
        if not token:
            return None, None, "GitHub Copilot token not available. Connect on the Settings page."

        endpoint = settings.GITHUBCOPILOT_ENDPOINT.rstrip("/")
        client = OpenAI(
            api_key=token,
            base_url=endpoint,
            http_client=http_client,
            default_headers={
                "Editor-Version": "vscode/1.98.0",
                "Editor-Plugin-Version": "copilot-chat/0.26.7",
                "Copilot-Integration-Id": "vscode-chat",
                "User-Agent": "GitHubCopilotChat/0.26.7",
            },
        )
        return client, _resolve_model(), None

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            return None, None, "OPENAI_API_KEY not set"
        http_client = httpx.Client(verify=verify, timeout=float(settings.AI_HTTP_TIMEOUT_SECONDS))
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client)
        return client, _resolve_model(), None

    if provider in ("azure", "azureopenai"):
        if not settings.AZURE_OPENAI_BASE_URL or not settings.AZURE_OPENAI_API_KEY:
            return None, None, "Azure OpenAI not configured"
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_BASE_URL,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        return client, _resolve_model(), None

    return None, None, f"Unknown AI provider: {provider}"


def _chat_completion(client, model: str, messages: List[Dict], temperature: float, max_tokens: int):
    """Call chat completion with model fallback."""
    call_args = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "model": model}
    try:
        return client.chat.completions.create(**call_args)
    except Exception as e:
        if _is_model_not_supported(e) and "gpt-4o" not in model.lower():
            call_args["model"] = "gpt-4o"
            return client.chat.completions.create(**call_args)
        raise


async def ai_chat(
    messages: List[Dict],
    system_context: str = "",
    attachments: Optional[List[Dict]] = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """Multi-turn chat completion.

    messages: list of {"role": "user"/"assistant", "content": "..."}
    system_context: extra context appended to the system prompt
    attachments: list of {"name": str, "type": str, "content": str}
    """
    client, model, err = _get_client()
    if not client:
        return {"error": err or "AI not configured"}

    system_msg = (
        "You are IntelliTest AI, an expert test generation assistant for data engineering teams. "
        "You generate SQL-based validation tests for ETL pipelines, data warehouses, and financial "
        "data systems. Use Oracle/Redshift syntax as appropriate. When generating tests, produce "
        "complete, executable SQL SELECT statements that return mismatches (0 rows = pass). "
        "Include both simple column checks and multi-layer aggregation validations. "
        "Reference Jira/TFS requirements and DRD mappings when provided."
    )
    if system_context:
        system_msg += f"\n\nContext:\n{system_context}"

    all_messages = [{"role": "system", "content": system_msg}]

    if attachments:
        att_text = "\n\n".join(
            f"=== {a.get('name', 'File')} ({a.get('type', '')}) ===\n{a.get('content', '')[:3000]}"
            for a in attachments
        )
        all_messages.append({
            "role": "user",
            "content": f"Use the following attached files as context:\n\n{att_text}",
        })

    all_messages.extend(messages)

    try:
        resp = _chat_completion(client, model, all_messages, temperature, max_tokens)
        return {"reply": resp.choices[0].message.content.strip()}
    except Exception as e:
        logger.exception("AI chat error")
        return {"error": str(e)}


async def ai_generate_tests(
    context: str,
    target_table: str = "",
    source_table: str = "",
    mapping_rows: Optional[List[Dict]] = None,
    jira_context: Optional[Dict] = None,
    tfs_context: Optional[Dict] = None,
    multi_layer: bool = True,
) -> Dict[str, Any]:
    """Generate SQL validation tests from mapping context.

    Returns: {"tests": [...], "error": "..." if failed}
    """
    parts = [
        f"Generate SQL validation test cases for the following ETL mapping.\n"
        f"Target table: {target_table or 'not specified'}\n"
        f"Source table: {source_table or 'not specified'}\n"
    ]
    if context:
        parts.append(f"Context:\n{context}")
    if mapping_rows:
        rows_text = "\n".join(
            f"- {r.get('physical_name', '')} ← {r.get('source_table', '')}.{r.get('source_attribute', '')} "
            f"[{r.get('transformation', 'direct')}]"
            for r in mapping_rows[:50]
        )
        parts.append(f"Mapping rows:\n{rows_text}")
    if jira_context:
        parts.append(
            f"Jira requirement: {jira_context.get('key', '')} — {jira_context.get('summary', '')}\n"
            f"Acceptance criteria: {jira_context.get('acceptance_criteria', '')[:500]}"
        )
    if tfs_context:
        parts.append(
            f"TFS requirement: #{tfs_context.get('id', '')} — {tfs_context.get('title', '')}\n"
            f"Acceptance criteria: {tfs_context.get('acceptance_criteria', '')[:500]}"
        )
    if multi_layer:
        parts.append(
            "\nInclude MULTI-LAYER tests:\n"
            "1. Source staging → first aggregation/transformation layer\n"
            "2. Intermediate layer → final target\n"
            "3. Column-level value comparison tests\n"
            "4. Aggregate total validation tests\n"
            "5. NULL/empty checks\n"
            "6. Grain/duplicate key tests"
        )

    prompt = "\n\n".join(parts)
    prompt += (
        "\n\nReturn a JSON array of test objects, each with:"
        ' {"name": "...", "description": "...", "category": "grain|null|aggregate|column|multi_layer",'
        ' "severity": "critical|high|medium|low", "source_query": "SELECT...", "target_query": "SELECT...",'
        ' "test_type": "value_match|count_match|aggregate_match|custom"}'
    )

    result = await ai_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=5000,
    )
    if "error" in result:
        return {"error": result["error"], "tests": []}

    # Parse JSON from response
    reply = result.get("reply", "")
    tests = _extract_json_tests(reply)
    return {"tests": tests, "raw_response": reply}


def _extract_json_tests(text: str) -> List[Dict]:
    """Extract a JSON array of test cases from AI response text."""
    if not text:
        return []
    # Try to find a JSON array
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            import json
            return json.loads(match.group())
        except Exception:
            pass
    return []
