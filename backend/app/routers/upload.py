"""5.1 Upload endpoint (async ingestion via BackgroundTasks) and
5.3 status endpoint, 5.4 sources listing endpoint."""

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Response, UploadFile

from app.config import settings
from app.db import repository
from app.ingestion.pipeline import run_ingestion
from app.ingestion.source_type import UnsupportedSourceTypeError, infer_source_type

router = APIRouter(prefix="/projects/{project_id}", tags=["ingestion"])


def _slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-")
    return name or "source"


@router.post("/upload")
async def upload_source(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    source_type: Optional[str] = Form(None),
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="Provide either a file or a url")

    try:
        resolved_type = infer_source_type(
            filename=file.filename if file else None, url=url, explicit=source_type
        )
    except UnsupportedSourceTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if file:
        source_id = _slugify(file.filename or "upload")
        original_name = file.filename
        project_dir = Path(settings.upload_dir) / project_id / "raw"
        project_dir.mkdir(parents=True, exist_ok=True)
        dest_path = project_dir / source_id
        with dest_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        path_or_url = str(dest_path)
        title = original_name
    else:
        source_id = _slugify(url)
        original_name = url
        path_or_url = url
        title = url

    job_id = await repository.create_ingestion_job(
        project_id, source_id, resolved_type, original_name
    )

    background_tasks.add_task(
        run_ingestion,
        job_id=job_id,
        project_id=project_id,
        source_id=source_id,
        source_type=resolved_type,
        path_or_url=path_or_url,
        title=title,
    )

    return {"job_id": job_id, "source_id": source_id, "source_type": resolved_type, "status": "processing"}


@router.get("/status/{job_id}")
async def get_status(project_id: str, job_id: str):
    job = await repository.get_job_status(project_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": str(job["id"]),
        "source_id": job["source_id"],
        "source_type": job["source_type"],
        "status": job["status"],
        "chunk_count": job["chunk_count"],
        "error": job["error"],
    }


@router.get("/sources")
async def get_sources(project_id: str):
    sources = await repository.list_sources(project_id)
    return {"sources": sources}


def _remove_source_files(project_id: str, source_id: str) -> None:
    base = Path(settings.upload_dir) / project_id

    raw_file = base / "raw" / source_id
    if raw_file.is_file():
        raw_file.unlink(missing_ok=True)

    assets_dir = base / "assets" / source_id
    if assets_dir.is_dir():
        shutil.rmtree(assets_dir, ignore_errors=True)

    # Image sources store the asset as `assets/<source_id><ext>`.
    for asset_file in (base / "assets").glob(f"{source_id}.*"):
        if asset_file.is_file():
            asset_file.unlink(missing_ok=True)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(project_id: str, source_id: str):
    await repository.delete_source(project_id, source_id)
    _remove_source_files(project_id, source_id)
    return Response(status_code=204)
