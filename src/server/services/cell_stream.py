"""Live cell-execution streaming over Socket.IO.

Bridges :class:`KernelSandbox.execute_cell_streaming` callbacks to the
WebSocket events consumed by the Command Center Live panel:

  * ``cell_status``   — execution_state transitions (busy / idle)
  * ``cell_output``   — every IOPub message in nbformat shape
  * ``cell_complete`` — final result (success / error / killed_reason +
                         execution_count + duration_ms)

Each event carries a stable ``execution_id`` so the frontend can route
concurrent cell executions correctly (one panel can have multiple cells
in flight).

Audit logging happens in this module too — every cell execution writes a
``CellExecutionAudit`` row with a sha256 of the code and the policy name.
The full code is intentionally not stored for privacy/storage reasons.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from src.server.utils.socket_emitter import get_socket_manager
from src.services.kernel_session_manager import kernel_session_manager
from src.services.sandbox_executor import ExecutionResult
from src.utils.logger import get_logger

logger = get_logger()


def _emit(event: str, payload: Dict[str, Any], room: str) -> None:
    """Emit a Socket.IO event, swallowing any transport error.

    The emitter must never break execution — if Redis/Socket.IO is wedged
    the cell still runs and the caller still gets the aggregate result.
    """
    try:
        get_socket_manager().emit(event, payload, room=room)
    except Exception as e:
        logger.debug(f"Socket emit '{event}' failed: {e}")


def _audit(
    *,
    job_id: str,
    user_id: Optional[str],
    code: str,
    result: ExecutionResult,
    policy_name: str,
) -> None:
    """Persist a CellExecutionAudit row. Best-effort — never raises."""
    try:
        from src.server.db.database import SessionLocal
        from src.server.db.models import CellExecutionAudit

        with SessionLocal() as session:
            session.add(
                CellExecutionAudit(
                    job_id=job_id,
                    user_id=user_id,
                    code_hash=hashlib.sha256(code.encode("utf-8", errors="ignore")).hexdigest(),
                    code_length=len(code),
                    duration_ms=result.duration_ms,
                    success=result.success,
                    error_name=result.error_name,
                    killed_reason=result.killed_reason,
                    policy_name=policy_name,
                )
            )
            session.commit()
    except Exception as e:
        logger.debug(f"CellExecutionAudit write failed: {e}")


def stream_execute(
    *,
    job_id: str,
    execution_id: str,
    code: str,
    user_id: Optional[str] = None,
) -> ExecutionResult:
    """Execute ``code`` in the given job's kernel, streaming events to the
    job's Socket.IO room.

    Emits, in order:
      1. ``cell_status`` running          (before kernel starts the cell)
      2. ``cell_output`` × N              (each IOPub message)
      3. ``cell_complete`` final result   (with execution_count, success,
                                            duration_ms, killed_reason)

    Returns the aggregate :class:`ExecutionResult` as well so callers that
    don't want to subscribe to WS can still read the outcome (used by tests
    and the legacy synchronous cell-edit path).
    """
    room = job_id

    # Resolve the session: caller is expected to have already created one
    # (typically via ``kernel_session_manager.get_or_create_session`` in
    # the route handler). If absent, we report the error via WS + result.
    session = kernel_session_manager.get_session(job_id)
    if session is None:
        result = ExecutionResult()
        result.success = False
        result.error_name = "NoSession"
        result.error_value = (
            "No active kernel session for this job. "
            "Initialise one before calling stream_execute()."
        )
        _emit("cell_complete", {
            "execution_id": execution_id,
            "job_id": job_id,
            "success": False,
            "error_name": result.error_name,
            "error_value": result.error_value,
            "duration_ms": 0,
        }, room=room)
        return result

    policy_name = "production"
    try:
        sandbox = getattr(session.executor, "_sandbox", None) if session.executor else None
        if sandbox is not None:
            policy_name = sandbox.policy.name
    except Exception:
        pass

    _emit("cell_status", {
        "execution_id": execution_id,
        "job_id": job_id,
        "execution_state": "busy",
    }, room=room)

    def _on_output(event: Dict[str, Any]) -> None:
        # Forward status separately so frontend cell controls can flip
        # the per-cell "running" indicator between the start-of-cell
        # busy and the end-of-cell idle.
        if event.get("output_type") == "status":
            _emit("cell_status", {
                "execution_id": execution_id,
                "job_id": job_id,
                "execution_state": event.get("execution_state"),
            }, room=room)
            return
        _emit("cell_output", {
            "execution_id": execution_id,
            "job_id": job_id,
            "output": event,
        }, room=room)

    try:
        result = session.execute_streaming(code, on_output=_on_output)
    except Exception as e:
        logger.error(f"stream_execute crashed for {job_id}/{execution_id}: {e}")
        result = ExecutionResult()
        result.success = False
        result.error_name = "StreamExecuteCrash"
        result.error_value = str(e)

    _emit("cell_complete", {
        "execution_id": execution_id,
        "job_id": job_id,
        "success": result.success,
        "error_name": result.error_name,
        "error_value": result.error_value,
        "execution_count": result.execution_count,
        "duration_ms": result.duration_ms,
        "killed_reason": result.killed_reason,
    }, room=room)

    _audit(
        job_id=job_id,
        user_id=user_id,
        code=code,
        result=result,
        policy_name=policy_name,
    )

    return result
