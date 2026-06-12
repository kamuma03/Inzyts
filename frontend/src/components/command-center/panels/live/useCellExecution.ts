import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import { AnalysisAPI } from '../../../../api';
import { newExecutionId } from './cellHelpers';
import type { LiveCell } from './types';

interface UseCellExecutionArgs {
    jobId: string;
    /** Mirror of the latest `cells` so callbacks stay referentially stable. */
    cellsRef: MutableRefObject<LiveCell[]>;
    /** execution_id → cell_id map so streamed WS events route correctly. */
    executionToCellRef: MutableRefObject<Map<string, string>>;
    /** Immutable single-cell patch. */
    updateCell: (
        cellId: string,
        patch: Partial<LiveCell> | ((c: LiveCell) => Partial<LiveCell>),
    ) => void;
    setCells: Dispatch<SetStateAction<LiveCell[]>>;
    setRestartPending: Dispatch<SetStateAction<boolean>>;
}

interface UseCellExecutionResult {
    runCell: (cellId: string) => Promise<void>;
    runAll: () => Promise<void>;
    runAbove: (cellId: string) => Promise<void> | void;
    runBelow: (cellId: string) => Promise<void> | void;
    stopCell: () => Promise<void>;
    restartKernel: () => Promise<void>;
}

/** Owns the per-cell execution lifecycle: queueing a run, the HTTP-response
 *  fallback finalization (used when the Socket.IO stream is unreachable),
 *  Run-All/Above/Below, interrupt, and restart. The WS event handlers
 *  (cell_status / cell_output / cell_complete) stay in LivePanel because they
 *  also drive save-back / tweak state, but they share the same
 *  `executionToCellRef` mapping written here. */
export function useCellExecution({
    jobId,
    cellsRef,
    executionToCellRef,
    updateCell,
    setCells,
    setRestartPending,
}: UseCellExecutionArgs): UseCellExecutionResult {
    // Begin a kernel run for one code cell: register the execution mapping and
    // reset the cell to `queued`. Returns the execution id so the caller can
    // finalize/clean up.
    const beginRun = useCallback(
        (cellId: string): string => {
            const execId = newExecutionId();
            executionToCellRef.current.set(execId, cellId);
            updateCell(cellId, {
                outputs: [],
                state: 'queued',
                error_name: null,
                error_value: null,
                killed_reason: null,
            });
            return execId;
        },
        [executionToCellRef, updateCell],
    );

    // Shared HTTP-response fallback finalizer for runCell and runMany. The
    // /cells/execute response carries the aggregate outcome (success,
    // error_name/value, execution_count, duration_ms). We use it to finalize
    // the cell when the Socket.IO stream is unreachable (e.g. Redis pubsub
    // down, dev proxy not forwarding WS) — otherwise the cell would hang in
    // `queued` even after the kernel finished. We do NOT delete the execution
    // mapping here: a WS cell_complete may still arrive after the HTTP
    // response and is the canonical cleanup point; the mapping evaporates when
    // cell_complete fires.
    const finalizeFromHttp = useCallback(
        (cellId: string, res: Awaited<ReturnType<typeof AnalysisAPI.executeLiveCell>>) => {
            setCells((prev) =>
                prev.map((c) => {
                    if (c.id !== cellId) return c;
                    // If a WS cell_complete already finalized the cell, leave
                    // it alone — the live stream is authoritative when present.
                    if (c.state !== 'queued' && c.state !== 'busy') return c;
                    const finalized: Partial<LiveCell> = {
                        state: res.success ? 'idle' : 'error',
                        execution_count: res.execution_count,
                        error_name: res.error_name,
                        error_value: res.error_value,
                        duration_ms: res.duration_ms,
                        killed_reason: res.killed_reason,
                    };
                    // If we never received any cell_output events but the run
                    // produced an error, synthesise an error output so the user
                    // sees what went wrong instead of an empty cell.
                    if (!res.success && c.outputs.length === 0 && (res.error_name || res.error_value)) {
                        finalized.outputs = [{
                            output_type: 'error',
                            ename: res.error_name ?? 'Error',
                            evalue: res.error_value ?? '',
                            traceback: [],
                        }];
                    }
                    return { ...c, ...finalized };
                }),
            );
        },
        [setCells],
    );

    // Shared error path: the HTTP request itself failed (network / non-2xx).
    // The execution will never stream, so drop the mapping and surface the
    // failure as an error output.
    const failFromHttp = useCallback(
        (cellId: string, execId: string, e: unknown) => {
            executionToCellRef.current.delete(execId);
            const msg = e instanceof Error ? e.message : String(e);
            updateCell(cellId, {
                state: 'error',
                error_name: 'RequestFailed',
                error_value: msg,
                outputs: [{
                    output_type: 'error',
                    ename: 'RequestFailed',
                    evalue: msg,
                    traceback: [],
                }],
            });
        },
        [executionToCellRef, updateCell],
    );

    const runCell = useCallback(async (cellId: string) => {
        const cell = cellsRef.current.find((c) => c.id === cellId);
        if (!cell || cell.state === 'busy') return;

        // Markdown cells just collapse the editor back to the preview.
        if (cell.cell_type === 'markdown') {
            updateCell(cellId, { md_editing: false });
            return;
        }

        const execId = beginRun(cellId);
        try {
            const res = await AnalysisAPI.executeLiveCell(jobId, cell.code, execId);
            finalizeFromHttp(cellId, res);
        } catch (e) {
            failFromHttp(cellId, execId, e);
        }
    }, [jobId, cellsRef, updateCell, beginRun, finalizeFromHttp, failFromHttp]);

    const stopCell = useCallback(async () => {
        try {
            await AnalysisAPI.interruptLiveKernel(jobId);
        } catch {
            // No active session is not an error worth surfacing — the cell
            // may have already finished by the time the user clicked.
        }
    }, [jobId]);

    const restartKernel = useCallback(async () => {
        setRestartPending(true);
        try {
            await AnalysisAPI.restartLiveKernel(jobId);
            // Clear all outputs and execution counts.
            setCells((prev) => prev.map((c) => ({
                ...c,
                outputs: [],
                state: 'idle',
                execution_count: null,
                error_name: null,
                error_value: null,
                duration_ms: null,
                killed_reason: null,
            })));
            executionToCellRef.current.clear();
        } catch {
            // No session yet → effectively a fresh start. Same UX outcome.
        } finally {
            setRestartPending(false);
        }
    }, [jobId, setCells, setRestartPending, executionToCellRef]);

    // -- Run All / Above / Below --------------------------------------------
    // The kernel serializes execution per job, so we can fire requests in
    // order; the server-side cell_stream will deliver outputs back to each
    // cell via the execution_id mapping. We deliberately do not await each
    // run inside the loop — the kernel queues them on its side.

    const runMany = useCallback(async (targets: LiveCell[]) => {
        for (const c of targets) {
            if (c.cell_type !== 'code') continue;
            const execId = beginRun(c.id);
            try {
                const res = await AnalysisAPI.executeLiveCell(jobId, c.code, execId);
                // Same HTTP fallback as runCell — mapping is kept so late WS
                // events still resolve.
                finalizeFromHttp(c.id, res);
            } catch (e) {
                failFromHttp(c.id, execId, e);
            }
        }
    }, [jobId, beginRun, finalizeFromHttp, failFromHttp]);

    const runAll = useCallback(() => runMany(cellsRef.current), [runMany, cellsRef]);

    const runAbove = useCallback((cellId: string) => {
        const current = cellsRef.current;
        const idx = current.findIndex((c) => c.id === cellId);
        if (idx <= 0) return;
        return runMany(current.slice(0, idx));
    }, [runMany, cellsRef]);

    const runBelow = useCallback((cellId: string) => {
        const current = cellsRef.current;
        const idx = current.findIndex((c) => c.id === cellId);
        if (idx === -1) return;
        return runMany(current.slice(idx));
    }, [runMany, cellsRef]);

    return { runCell, runAll, runAbove, runBelow, stopCell, restartKernel };
}
