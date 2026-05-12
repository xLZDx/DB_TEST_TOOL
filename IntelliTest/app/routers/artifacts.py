"""Artifact upload router – standalone entry point for file management."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.post("/upload")
async def upload(file: UploadFile = File(...),
                  conversation_id: Optional[str] = Form(default=None)):
    from app.routers.chat import _extract_text, _guess_type
    from app.services.artifact_memory import save_artifact, link_artifact
    raw = await file.read()
    fname = file.filename or "upload"
    text = _extract_text(fname, raw)
    art_type = _guess_type(fname)
    art = save_artifact(fname, text, art_type, {"size": len(raw)})
    if conversation_id:
        link_artifact(conversation_id, art["id"])
    return {"ok": True, "artifact": art}


@router.get("/")
async def list_artifacts():
    from app.services.artifact_memory import list_artifacts
    return {"artifacts": list_artifacts()}


@router.delete("/{art_id}")
async def delete(art_id: str):
    from app.services.artifact_memory import delete_artifact
    if delete_artifact(art_id):
        return {"ok": True}
    raise HTTPException(404, "Not found")


@router.get("/{art_id}/preview")
async def preview(art_id: str, max_chars: int = 2000):
    from app.services.artifact_memory import get_artifact_content
    c = get_artifact_content(art_id)
    if c is None:
        raise HTTPException(404, "Not found")
    return {"preview": c[:max_chars], "total_length": len(c)}
