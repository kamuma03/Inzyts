from fastapi import APIRouter, HTTPException, Depends, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import nbformat
from nbconvert import HTMLExporter
from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import Job, ConversationMessage
from src.server.middleware.auth import verify_token, verify_token_async
from src.server.models.schemas import (
    CellEditRequest,
    CellEditResponse,
    FollowUpRequest,
    FollowUpResponse,
    FollowUpCell,
    ConversationHistoryResponse,
    ConversationMessageSchema,
)
from src.server.services.jupyter_proxy import jupyter_service
from src.utils.logger import get_logger
from src.utils.path_validator import validate_path_within

logger = get_logger()

router = APIRouter(prefix="/notebooks", tags=["notebooks"])

# Allowed base directory for notebook output files.
_OUTPUT_DIR = settings.output_dir_resolved


def _validate_notebook_path(notebook_path: Path) -> None:
    """Raise HTTPException if notebook_path is outside the allowed output directory."""
    validate_path_within(
        notebook_path,
        [_OUTPUT_DIR],
        error_label="notebook",
    )


@router.get("/jupyter-token")
async def get_jupyter_token(_token: str = Depends(verify_token)):
    """Return the Jupyter token for authenticated users to access Live Notebook."""
    from src.config import settings
    if not settings.jupyter.token:
        raise HTTPException(status_code=404, detail="Jupyter token not configured")
    return {"token": settings.jupyter.token}


@router.get("/{job_id}/html")
async def get_notebook_html(
    job_id: str, db: AsyncSession = Depends(get_db), _token: str = Depends(verify_token)
):
    """
    Retrieve the generated Jupyter Notebook for a job and convert it to HTML.
    """
    try:
        # 1. Get Job
        result = await db.execute(select(Job).filter(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if not job.result_path:
            raise HTTPException(
                status_code=404, detail="No notebook generated for this job yet"
            )

        notebook_path = Path(job.result_path)
        _validate_notebook_path(notebook_path)
        if not notebook_path.exists():
            raise HTTPException(
                status_code=404, detail="Notebook file not found"
            )

        # 2. Convert to HTML
        try:
            # Read notebook
            with open(notebook_path, "r", encoding="utf-8") as f:
                nb = nbformat.read(f, as_version=4)

            # Configure exporter
            html_exporter = HTMLExporter()
            # html_exporter.template_name = 'classic' # or 'lab' for more modern look, checking availability

            # Convert
            (body, resources) = html_exporter.from_notebook_node(nb)

            return {"html": body, "job_id": job_id}
        except Exception as e:
            logger.error(f"Notebook render error for job {job_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to render notebook"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notebook fetch error for job {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to render notebook"
        )


@router.get("/{job_id}/download")
async def download_notebook(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """Download the generated Jupyter Notebook (.ipynb) file."""
    from fastapi.responses import FileResponse

    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.result_path:
        raise HTTPException(
            status_code=404, detail="No notebook generated for this job yet"
        )

    notebook_path = Path(job.result_path)
    _validate_notebook_path(notebook_path)
    if not notebook_path.exists():
        raise HTTPException(status_code=404, detail="Notebook file not found")

    return FileResponse(
        path=str(notebook_path),
        media_type="application/x-ipynb+json",
        filename=notebook_path.name,
    )





@router.post("/{job_id}/session")
async def create_live_session(
    job_id: str, db: AsyncSession = Depends(get_db), _token: str = Depends(verify_token)
):
    """
    Start a live Jupyter kernel for this notebook.
    """
    try:
        # Check integrity
        status = await jupyter_service.get_status()
        if status.get("status") == "unreachable":
            raise HTTPException(status_code=503, detail="Jupyter Service unavailable")

        # Create kernel
        kernel_id = await jupyter_service.create_kernel()

        return {"job_id": job_id, "kernel_id": kernel_id, "status": "ready"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create live session for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create live session")


@router.websocket("/{job_id}/ws/{kernel_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str, kernel_id: str):
    """
    WebSocket proxy for live kernel communication.
    Token is required as a query parameter: ?token=<JWT>
    """
    from src.server.db.database import async_session_maker
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4003, reason="No token provided")
        return
    async with async_session_maker() as db:
        user = await verify_token_async(token, db)
    if not user:
        await websocket.close(code=4003, reason="Invalid token")
        return
    await websocket.accept()
    await jupyter_service.proxy_websocket(websocket, kernel_id)


@router.get("/{job_id}/cells")
async def get_notebook_cells(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """
    Retrieve the notebook as structured JSON cells (for interactive mode).
    """
    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.result_path:
        raise HTTPException(status_code=404, detail="No notebook generated for this job")

    notebook_path = Path(job.result_path)
    _validate_notebook_path(notebook_path)
    if not notebook_path.exists():
        raise HTTPException(status_code=404, detail="Notebook file not found")

    try:
        with open(notebook_path, "r", encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        cells = []
        for cell in nb.cells:
            cell_data = {
                "cell_type": cell.cell_type,
                "source": cell.source,
                "outputs": [],
            }
            # Parse outputs for code cells
            if cell.cell_type == "code" and hasattr(cell, "outputs"):
                for output in cell.outputs:
                    out = {"output_type": output.get("output_type", "unknown")}
                    if output.get("output_type") == "stream":
                        out["text"] = output.get("text", "")
                    elif output.get("output_type") in ("display_data", "execute_result"):
                        data = output.get("data", {})
                        if "image/png" in data:
                            out["data"] = {"image/png": data["image/png"]}
                        if "text/plain" in data:
                            out["text"] = data["text/plain"]
                    elif output.get("output_type") == "error":
                        out["text"] = "\n".join(output.get("traceback", []))
                    cell_data["outputs"].append(out)
            cells.append(cell_data)

        return {"cells": cells, "job_id": job_id}
    except Exception as e:
        logger.error(f"Failed to parse notebook for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse notebook")


@router.post("/{job_id}/cells/edit")
async def edit_cell(
    job_id: str,
    request: CellEditRequest,
    db: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """
    Edit a notebook cell using natural language instruction.

    Uses CellEditAgent to modify the code, then executes it in a persistent kernel.
    """
    from src.services.kernel_session_manager import kernel_session_manager
    from src.workflow.agent_factory import AgentFactory

    # 1. Verify job exists
    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    csv_path = job.csv_path or ""

    try:
        # 2. Get or create kernel session
        session = kernel_session_manager.get_or_create_session(job_id, csv_path)

        # 3. Use CellEditAgent to generate modified code
        agent = AgentFactory.get_agent("cell_edit")
        edit_result = agent.edit_cell(
            instruction=request.instruction,
            current_code=request.current_code,
            df_context=session.df_context,
        )

        if not edit_result["success"]:
            return CellEditResponse(
                new_code=request.current_code,
                output="",
                images=[],
                success=False,
                error=edit_result.get("error", "Agent failed to generate code"),
            )

        new_code = edit_result["new_code"]

        # 4. Execute the new code in the kernel
        exec_result = session.execute(new_code)

        return CellEditResponse(
            new_code=new_code,
            output=exec_result.output,
            images=exec_result.images,
            success=exec_result.success,
            error=exec_result.error_value if not exec_result.success else None,
        )

    except Exception as e:
        logger.error(f"Cell edit failed for job {job_id}: {e}")
        return CellEditResponse(
            new_code=request.current_code,
            output="",
            images=[],
            success=False,
            error=f"Cell edit failed: {type(e).__name__}",
        )


@router.post("/{job_id}/ask")
async def ask_followup(
    job_id: str,
    request: FollowUpRequest,
    db: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """
    Ask a follow-up question about a completed analysis.

    Generates new notebook cells, executes them in a persistent kernel,
    and persists the conversation to the database.
    """
    from src.services.kernel_session_manager import kernel_session_manager
    from src.workflow.agent_factory import AgentFactory

    # 1. Verify job exists
    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    csv_path = job.csv_path or ""

    try:
        # 2. Load conversation history from DB
        history_result = await db.execute(
            select(ConversationMessage)
            .filter(ConversationMessage.job_id == job_id)
            .order_by(ConversationMessage.created_at)
        )
        history_rows = history_result.scalars().all()
        conversation_history = [
            {"role": row.role, "content": row.content}
            for row in history_rows
        ]

        # 3. Get or create kernel session
        session = kernel_session_manager.get_or_create_session(job_id, csv_path)

        # 4. Introspect kernel state
        kernel_context = session.introspect()

        # 5. Build notebook summary from existing cells
        notebook_summary = f"Analysis notebook for {csv_path}"
        if job.mode:
            notebook_summary += f" (mode: {job.mode})"
        if job.question:
            notebook_summary += f" — Question: {job.question}"

        # 6. Call FollowUpAgent
        agent = AgentFactory.get_agent("follow_up")
        agent_result = agent.ask(
            question=request.question,
            df_context=session.df_context,
            kernel_context=kernel_context,
            notebook_summary=notebook_summary,
            conversation_history=conversation_history,
        )

        if not agent_result["success"]:
            return FollowUpResponse(
                summary="",
                cells=[],
                success=False,
                error=agent_result.get("error", "Agent failed"),
                conversation_length=len(history_rows) // 2,
            )

        # 7. Execute each code cell in the kernel
        executed_cells = []
        for cell in agent_result.get("cells", []):
            cell_type = cell.get("cell_type", "markdown")
            source = cell.get("source", "")

            if cell_type == "code" and source.strip():
                exec_result = session.execute(source)
                executed_cells.append(
                    FollowUpCell(
                        cell_type="code",
                        source=source,
                        output=exec_result.output or "",
                        images=exec_result.images if hasattr(exec_result, "images") else [],
                    )
                )
            else:
                executed_cells.append(
                    FollowUpCell(cell_type=cell_type, source=source)
                )

        # 8. Persist to DB: user message
        user_msg = ConversationMessage(
            job_id=job_id,
            role="user",
            content=request.question,
        )
        db.add(user_msg)

        # 9. Persist to DB: assistant message
        assistant_msg = ConversationMessage(
            job_id=job_id,
            role="assistant",
            content=agent_result.get("summary", ""),
            cells=[c.model_dump() for c in executed_cells],
        )
        db.add(assistant_msg)
        await db.commit()

        # Count total exchanges
        total_messages = len(history_rows) + 2  # existing + new user + assistant
        conversation_length = total_messages // 2

        return FollowUpResponse(
            summary=agent_result.get("summary", ""),
            cells=executed_cells,
            success=True,
            error=None,
            conversation_length=conversation_length,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Follow-up failed for job {job_id}: {e}")
        return FollowUpResponse(
            summary="",
            cells=[],
            success=False,
            error=f"Follow-up failed: {type(e).__name__}",
            conversation_length=0,
        )


@router.get("/{job_id}/conversation")
async def get_conversation_history(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """
    Load the full conversation history for a job.

    Returns all follow-up Q&A exchanges in chronological order,
    enabling the frontend to restore conversations on page load.
    """
    # Verify job exists
    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load messages
    history_result = await db.execute(
        select(ConversationMessage)
        .filter(ConversationMessage.job_id == job_id)
        .order_by(ConversationMessage.created_at)
    )
    rows = history_result.scalars().all()

    messages = []
    for row in rows:
        cells = None
        if row.cells:
            cells = [FollowUpCell(**c) for c in row.cells]

        messages.append(
            ConversationMessageSchema(
                role=row.role,
                content=row.content,
                cells=cells,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )

    return ConversationHistoryResponse(job_id=job_id, messages=messages)
