import { useCallback, useEffect, useRef, useState, type FC } from 'react';
import { Play, RotateCcw, StopCircle, Plus, Loader2 } from 'lucide-react';
import { AnalysisAPI } from '../../../../api';
import { useSocket } from '../../../../hooks/useSocket';
import { CellOutputView } from './outputs/CellOutputView';
import type {
    CellCompleteEvent,
    CellOutput,
    CellOutputEvent,
    CellStatusEvent,
    LiveCell,
} from './types';

interface LivePanelProps {
    jobId: string;
    /** Initial cell sources to populate the panel — typically the
     *  generated notebook's code cells. */
    initialCells?: string[];
}

const newCellId = (): string =>
    `cell-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const newExecutionId = (): string =>
    `exec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const makeCell = (code: string): LiveCell => ({
    id: newCellId(),
    code,
    outputs: [],
    state: 'idle',
    execution_count: null,
    error_name: null,
    error_value: null,
    duration_ms: null,
    killed_reason: null,
});

/** Native Inzyts replacement for the Jupyter Lab iframe.
 *
 *  Renders the job's notebook cells as discrete blocks with per-cell
 *  Run/Stop controls, talks to the PR1 sandbox API for execution, and
 *  streams output via the cell_status / cell_output / cell_complete WS
 *  events emitted by ``cell_stream.py``. */
export const LivePanel: FC<LivePanelProps> = ({ jobId, initialCells = [] }) => {
    const [cells, setCells] = useState<LiveCell[]>(() =>
        initialCells.length > 0
            ? initialCells.map(makeCell)
            : [makeCell('# Enter code here\n')],
    );
    const [restartPending, setRestartPending] = useState(false);
    // Map execution_id → cell_id so streamed events route correctly.
    const executionToCellRef = useRef<Map<string, string>>(new Map());

    // Update a cell by id, immutably.
    const updateCell = useCallback(
        (cellId: string, patch: Partial<LiveCell> | ((c: LiveCell) => Partial<LiveCell>)) => {
            setCells((prev) =>
                prev.map((c) => {
                    if (c.id !== cellId) return c;
                    const p = typeof patch === 'function' ? patch(c) : patch;
                    return { ...c, ...p };
                }),
            );
        },
        [],
    );

    const appendOutput = useCallback(
        (cellId: string, output: CellOutput) => {
            setCells((prev) =>
                prev.map((c) => {
                    if (c.id !== cellId) return c;
                    return { ...c, outputs: [...c.outputs, output] };
                }),
            );
        },
        [],
    );

    // -- WS handlers --------------------------------------------------------

    const onCellStatus = useCallback((evt: CellStatusEvent) => {
        const cellId = executionToCellRef.current.get(evt.execution_id);
        if (!cellId) return;
        if (evt.execution_state === 'busy') {
            updateCell(cellId, { state: 'busy' });
        }
        // `idle` is delivered as cell_complete too, so we don't flip back here
        // — it'd race with cell_complete's terminal patch.
    }, [updateCell]);

    const onCellOutput = useCallback((evt: CellOutputEvent) => {
        const cellId = executionToCellRef.current.get(evt.execution_id);
        if (!cellId) return;
        const output = evt.output;
        // Filter out the "status" pseudo-output forwarded by the backend.
        if ((output as { output_type?: string }).output_type === 'status') return;
        appendOutput(cellId, output as CellOutput);
    }, [appendOutput]);

    const onCellComplete = useCallback((evt: CellCompleteEvent) => {
        const cellId = executionToCellRef.current.get(evt.execution_id);
        if (!cellId) return;
        updateCell(cellId, {
            state: evt.success ? 'idle' : 'error',
            execution_count: evt.execution_count,
            error_name: evt.error_name,
            error_value: evt.error_value,
            duration_ms: evt.duration_ms,
            killed_reason: evt.killed_reason,
        });
        executionToCellRef.current.delete(evt.execution_id);
    }, [updateCell]);

    useSocket(jobId, { onCellStatus, onCellOutput, onCellComplete });

    // -- Cell controls ------------------------------------------------------

    const runCell = useCallback(async (cellId: string) => {
        const cell = cells.find((c) => c.id === cellId);
        if (!cell || cell.state === 'busy') return;

        const execId = newExecutionId();
        executionToCellRef.current.set(execId, cellId);
        // Clear previous outputs and mark queued; the WS busy event will
        // flip it to busy as soon as the kernel picks it up.
        updateCell(cellId, {
            outputs: [],
            state: 'queued',
            error_name: null,
            error_value: null,
            killed_reason: null,
        });
        try {
            await AnalysisAPI.executeLiveCell(jobId, cell.code, execId);
        } catch (e) {
            executionToCellRef.current.delete(execId);
            updateCell(cellId, {
                state: 'error',
                error_name: 'RequestFailed',
                error_value: e instanceof Error ? e.message : String(e),
            });
        }
    }, [cells, jobId, updateCell]);

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
    }, [jobId]);

    const addCell = useCallback(() => {
        setCells((prev) => [...prev, makeCell('# New cell\n')]);
    }, []);

    const updateCode = useCallback((cellId: string, code: string) => {
        updateCell(cellId, { code });
    }, [updateCell]);

    // Re-sync cells when the parent supplies a different initial set
    // (e.g., user navigates between jobs).
    useEffect(() => {
        if (initialCells.length === 0) return;
        setCells(initialCells.map(makeCell));
        executionToCellRef.current.clear();
    }, [jobId]);  // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div className="flex flex-col h-full min-h-0 bg-[var(--bg-deep-twilight)]">
            <header className="shrink-0 px-3 py-2 flex items-center gap-2 border-b border-[var(--border-color)]">
                <span className="text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                    Live notebook
                </span>
                <span className="ml-auto flex items-center gap-1.5">
                    <button
                        type="button"
                        onClick={addCell}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] rounded text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer"
                        aria-label="Add cell"
                    >
                        <Plus size={12} />
                        Cell
                    </button>
                    <button
                        type="button"
                        onClick={restartKernel}
                        disabled={restartPending}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] rounded text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] disabled:opacity-50 border-none bg-transparent cursor-pointer"
                        aria-label="Restart kernel"
                    >
                        {restartPending ? (
                            <Loader2 size={12} className="animate-spin" />
                        ) : (
                            <RotateCcw size={12} />
                        )}
                        Restart
                    </button>
                </span>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto">
                {cells.map((cell, idx) => (
                    <CellRow
                        key={cell.id}
                        index={idx}
                        cell={cell}
                        onCodeChange={(c) => updateCode(cell.id, c)}
                        onRun={() => runCell(cell.id)}
                        onStop={stopCell}
                    />
                ))}
            </div>
        </div>
    );
};

interface CellRowProps {
    index: number;
    cell: LiveCell;
    onCodeChange: (code: string) => void;
    onRun: () => void;
    onStop: () => void;
}

const CellRow: FC<CellRowProps> = ({ index, cell, onCodeChange, onRun, onStop }) => {
    const isBusy = cell.state === 'busy' || cell.state === 'queued';
    const isError = cell.state === 'error';

    const stateColor =
        cell.state === 'busy'
            ? 'var(--bg-turquoise-surf)'
            : cell.state === 'queued'
            ? 'var(--text-dim)'
            : isError
            ? 'var(--status-bad)'
            : 'var(--status-good)';

    return (
        <article className="border-b border-[var(--border-color)] last:border-b-0">
            <div className="flex items-stretch">
                {/* Gutter — execution count + state dot */}
                <div className="shrink-0 w-12 flex flex-col items-center pt-2 pb-1.5 gap-1">
                    <span
                        className={`inline-block w-1.5 h-1.5 rounded-full ${
                            isBusy ? 'animate-pulse' : ''
                        }`}
                        style={{ backgroundColor: stateColor }}
                        aria-label={`Cell ${index + 1} ${cell.state}`}
                    />
                    <span className="font-mono text-[10px] text-[var(--text-dim)]">
                        [{cell.execution_count ?? ' '}]
                    </span>
                </div>

                {/* Source editor */}
                <div className="flex-1 min-w-0 py-2 pr-2">
                    <textarea
                        value={cell.code}
                        onChange={(e) => onCodeChange(e.target.value)}
                        spellCheck={false}
                        rows={Math.min(20, Math.max(2, cell.code.split('\n').length))}
                        className="w-full font-mono text-[12px] leading-[1.4] bg-[var(--bg-true-cobalt)] text-[var(--text-primary)] border border-[var(--border-color)] rounded px-2 py-1.5 resize-y focus:outline-none focus:border-[var(--bg-turquoise-surf)]"
                        aria-label={`Cell ${index + 1} source`}
                    />

                    {/* Per-cell controls */}
                    <div className="flex items-center gap-1 mt-1">
                        {isBusy ? (
                            <button
                                type="button"
                                onClick={onStop}
                                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[rgba(248,113,113,0.1)] text-[var(--status-bad)] border border-[rgba(248,113,113,0.3)] cursor-pointer"
                                aria-label="Stop cell"
                            >
                                <StopCircle size={11} />
                                Stop
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={onRun}
                                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[rgba(76,201,240,0.1)] text-[var(--bg-turquoise-surf)] border border-[rgba(76,201,240,0.3)] cursor-pointer"
                                aria-label="Run cell"
                            >
                                <Play size={11} />
                                Run
                            </button>
                        )}
                        {cell.duration_ms != null && cell.state !== 'busy' && (
                            <span className="ml-2 font-mono text-[10px] text-[var(--text-dim)]">
                                {cell.duration_ms} ms
                            </span>
                        )}
                        {cell.killed_reason && (
                            <span className="ml-2 font-mono text-[10px] text-[var(--status-warn)]">
                                killed: {cell.killed_reason}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Outputs */}
            {cell.outputs.length > 0 && (
                <div className="ml-12 mr-2 mb-2 border-l-2 border-[var(--border-color)]">
                    {cell.outputs.map((output, i) => (
                        <CellOutputView key={i} output={output} />
                    ))}
                </div>
            )}
        </article>
    );
};
