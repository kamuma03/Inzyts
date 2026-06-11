import { memo, useCallback, useEffect, useMemo, useRef, useState, type FC } from 'react';
import { Play, RotateCcw, StopCircle, Plus, Loader2, Sparkles, Check, AlertTriangle, Pencil, ArrowUp, ArrowDown, Trash2, Code as CodeIcon, FileText, PlayCircle, Save } from 'lucide-react';
import { AnalysisAPI } from '../../../../api';
import { useSocket } from '../../../../hooks/useSocket';
import { formatMarkdown } from '../../../../utils/formatMarkdown';
import { getErrorMessage } from '../../../../utils/errorMessage';
import { useJobContext } from '../../../../context/JobContext';
import { CellOutputView } from './outputs/CellOutputView';
import { CellSourceEditor } from './CellSourceEditor';
import type {
    CellCompleteEvent,
    CellOutput,
    CellOutputEvent,
    CellStatusEvent,
    LiveCell,
    NotebookCellSeed,
} from './types';

interface LivePanelProps {
    jobId: string;
    /** Code-only seed (legacy). Each entry becomes a code cell. */
    initialCells?: string[];
    /** Preferred typed seed — supports code + markdown cells. */
    initialNotebookCells?: NotebookCellSeed[];
}

const newCellId = (): string =>
    `cell-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const newExecutionId = (): string =>
    `exec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const makeCell = (source: string, cell_type: 'code' | 'markdown' = 'code'): LiveCell => ({
    id: newCellId(),
    cell_type,
    code: source,
    outputs: [],
    state: 'idle',
    execution_count: null,
    error_name: null,
    error_value: null,
    duration_ms: null,
    killed_reason: null,
    md_editing: false,
    tweak_open: false,
    tweak_instruction: '',
    tweak_status: 'idle',
    tweak_error: null,
});

const seedToCells = (
    initialCells: string[] | undefined,
    initialNotebookCells: NotebookCellSeed[] | undefined,
): LiveCell[] => {
    if (initialNotebookCells && initialNotebookCells.length > 0) {
        return initialNotebookCells.map((c) => makeCell(c.source, c.cell_type));
    }
    if (initialCells && initialCells.length > 0) {
        return initialCells.map((s) => makeCell(s, 'code'));
    }
    return [makeCell('# Enter code here\n', 'code')];
};

/** Notebook surface — merges the AI-edit ("Editor") and live-kernel ("Sandbox")
 *  capabilities into one Jupyter-style cell stack.
 *
 *  Renders the job's notebook cells (code + markdown) as discrete blocks with
 *  per-cell Run/Stop, talks to the PR1 sandbox API for execution, and streams
 *  output via the cell_status / cell_output / cell_complete WS events. Each
 *  code cell also exposes a "Tweak" affordance that rewrites the source via
 *  the natural-language `editCell` agent. */
export const LivePanel: FC<LivePanelProps> = ({ jobId, initialCells, initialNotebookCells }) => {
    const { addToast } = useJobContext();
    const [cells, setCells] = useState<LiveCell[]>(() =>
        seedToCells(initialCells, initialNotebookCells),
    );
    // Mirror of `cells` so stable callbacks (run/tweak/save) can read the
    // latest cells without listing `cells` in their deps — that keeps the
    // per-row handlers referentially stable so React.memo on CellRow holds.
    const cellsRef = useRef(cells);
    cellsRef.current = cells;
    const [restartPending, setRestartPending] = useState(false);
    // Map execution_id → cell_id so streamed events route correctly.
    const executionToCellRef = useRef<Map<string, string>>(new Map());

    // Save-back state: `dirty` flips on every cell mutation (code, type,
    // structure); `saveStatus` drives the Save button's affordance.
    const [dirty, setDirty] = useState(false);
    // Ref mirror so stable callbacks can read the latest dirty flag without
    // depending on it (keeps per-row handlers referentially stable).
    const dirtyRef = useRef(dirty);
    dirtyRef.current = dirty;
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
    const [saveError, setSaveError] = useState<string | null>(null);
    const markDirty = useCallback(() => {
        setDirty(true);
        setSaveStatus('idle');
    }, []);

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
        const cell = cellsRef.current.find((c) => c.id === cellId);
        if (!cell || cell.state === 'busy') return;

        // Markdown cells just collapse the editor back to the preview.
        if (cell.cell_type === 'markdown') {
            updateCell(cellId, { md_editing: false });
            return;
        }

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
            // The /cells/execute response carries the aggregate outcome
            // (success, error_name/value, execution_count, duration_ms). We
            // use it as a fallback to finalize the cell when the Socket.IO
            // stream is unreachable (e.g. Redis pubsub down, dev proxy not
            // forwarding WS) — otherwise the cell would hang in `queued`
            // even after the kernel finished.
            const res = await AnalysisAPI.executeLiveCell(jobId, cell.code, execId);
            // Don't delete the execution mapping here — WS cell_complete may
            // still arrive after the HTTP response (and is the canonical
            // cleanup point). The mapping naturally evaporates when
            // cell_complete fires.
            setCells((prev) => prev.map((c) => {
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
            }));
        } catch (e) {
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
        }
    }, [jobId, updateCell]);

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
        setCells((prev) => [...prev, makeCell('# New cell\n', 'code')]);
        markDirty();
    }, [markDirty]);

    const updateCode = useCallback((cellId: string, code: string) => {
        updateCell(cellId, { code });
        markDirty();
    }, [updateCell, markDirty]);

    // -- Cell ops (Jupyter parity) ------------------------------------------

    const insertCellAfter = useCallback((cellId: string, cell_type: 'code' | 'markdown' = 'code') => {
        setCells((prev) => {
            const idx = prev.findIndex((c) => c.id === cellId);
            if (idx === -1) return prev;
            const next = [...prev];
            const seed = cell_type === 'markdown' ? '## New markdown cell\n' : '# New cell\n';
            next.splice(idx + 1, 0, makeCell(seed, cell_type));
            return next;
        });
        markDirty();
    }, [markDirty]);

    const insertCellBefore = useCallback((cellId: string, cell_type: 'code' | 'markdown' = 'code') => {
        setCells((prev) => {
            const idx = prev.findIndex((c) => c.id === cellId);
            if (idx === -1) return prev;
            const next = [...prev];
            const seed = cell_type === 'markdown' ? '## New markdown cell\n' : '# New cell\n';
            next.splice(idx, 0, makeCell(seed, cell_type));
            return next;
        });
        markDirty();
    }, [markDirty]);

    const deleteCell = useCallback((cellId: string) => {
        setCells((prev) => {
            // Refuse to drop the final cell — keep at least one editable
            // surface so the user has somewhere to land.
            if (prev.length <= 1) return prev;
            return prev.filter((c) => c.id !== cellId);
        });
        markDirty();
    }, [markDirty]);

    const moveCellUp = useCallback((cellId: string) => {
        setCells((prev) => {
            const idx = prev.findIndex((c) => c.id === cellId);
            if (idx <= 0) return prev;
            const next = [...prev];
            [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
            return next;
        });
        markDirty();
    }, [markDirty]);

    const moveCellDown = useCallback((cellId: string) => {
        setCells((prev) => {
            const idx = prev.findIndex((c) => c.id === cellId);
            if (idx === -1 || idx >= prev.length - 1) return prev;
            const next = [...prev];
            [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
            return next;
        });
        markDirty();
    }, [markDirty]);

    const toggleCellType = useCallback((cellId: string) => {
        updateCell(cellId, (c) => ({
            cell_type: c.cell_type === 'code' ? 'markdown' : 'code',
            outputs: [],
            execution_count: null,
            md_editing: c.cell_type === 'code',
        }));
        markDirty();
    }, [updateCell, markDirty]);

    // -- Run All / Above / Below --------------------------------------------
    // The kernel serializes execution per job, so we can fire requests in
    // order; the server-side cell_stream will deliver outputs back to each
    // cell via the execution_id mapping. We deliberately do not await each
    // run inside the loop — the kernel queues them on its side.

    const runMany = useCallback(async (targets: LiveCell[]) => {
        for (const c of targets) {
            if (c.cell_type !== 'code') continue;
            const execId = newExecutionId();
            executionToCellRef.current.set(execId, c.id);
            updateCell(c.id, {
                outputs: [],
                state: 'queued',
                error_name: null,
                error_value: null,
                killed_reason: null,
            });
            try {
                const res = await AnalysisAPI.executeLiveCell(jobId, c.code, execId);
                // Same HTTP fallback as runCell — see comment there. Mapping
                // is kept so late WS events still resolve.
                setCells((prev) => prev.map((cell) => {
                    if (cell.id !== c.id) return cell;
                    if (cell.state !== 'queued' && cell.state !== 'busy') return cell;
                    const finalized: Partial<LiveCell> = {
                        state: res.success ? 'idle' : 'error',
                        execution_count: res.execution_count,
                        error_name: res.error_name,
                        error_value: res.error_value,
                        duration_ms: res.duration_ms,
                        killed_reason: res.killed_reason,
                    };
                    if (!res.success && cell.outputs.length === 0 && (res.error_name || res.error_value)) {
                        finalized.outputs = [{
                            output_type: 'error',
                            ename: res.error_name ?? 'Error',
                            evalue: res.error_value ?? '',
                            traceback: [],
                        }];
                    }
                    return { ...cell, ...finalized };
                }));
            } catch (e) {
                executionToCellRef.current.delete(execId);
                const msg = e instanceof Error ? e.message : String(e);
                updateCell(c.id, {
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
            }
        }
    }, [jobId, updateCell]);

    const runAll = useCallback(() => runMany(cellsRef.current), [runMany]);

    const runAbove = useCallback((cellId: string) => {
        const current = cellsRef.current;
        const idx = current.findIndex((c) => c.id === cellId);
        if (idx <= 0) return;
        return runMany(current.slice(0, idx));
    }, [runMany]);

    const runBelow = useCallback((cellId: string) => {
        const current = cellsRef.current;
        const idx = current.findIndex((c) => c.id === cellId);
        if (idx === -1) return;
        return runMany(current.slice(idx));
    }, [runMany]);

    // -- Markdown edit / preview toggle -------------------------------------

    const setMdEditing = useCallback((cellId: string, editing: boolean) => {
        updateCell(cellId, { md_editing: editing });
    }, [updateCell]);

    // -- Save back to .ipynb ------------------------------------------------
    // Defined ahead of the Tweak handlers so an AI edit can persist the
    // current (possibly structurally-edited) notebook BEFORE the server-side
    // editCell runs against a cell index. Returns true on success.

    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const saveNotebook = useCallback(async (): Promise<boolean> => {
        setSaveStatus('saving');
        setSaveError(null);
        try {
            const payload = cellsRef.current.map((c) => ({
                cell_type: c.cell_type,
                source: c.code,
            }));
            await AnalysisAPI.saveNotebookCells(jobId, payload);
            setDirty(false);
            setSaveStatus('saved');
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
            saveTimerRef.current = setTimeout(() => setSaveStatus('idle'), 1500);
            return true;
        } catch (e) {
            setSaveStatus('error');
            setSaveError(getErrorMessage(e, 'Save failed'));
            return false;
        }
    }, [jobId]);

    const handleSave = useCallback(async () => {
        if (saveStatus === 'saving') return;
        await saveNotebook();
    }, [saveStatus, saveNotebook]);

    useEffect(() => {
        return () => {
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        };
    }, []);

    // -- Tweak (AI edit) ----------------------------------------------------

    const tweakTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    useEffect(() => {
        const timers = tweakTimersRef.current;
        return () => {
            timers.forEach((t) => clearTimeout(t));
            timers.clear();
        };
    }, []);

    const openTweak = useCallback((cellId: string) => {
        updateCell(cellId, { tweak_open: true, tweak_status: 'idle', tweak_error: null });
    }, [updateCell]);

    const closeTweak = useCallback((cellId: string) => {
        updateCell(cellId, { tweak_open: false, tweak_instruction: '', tweak_status: 'idle', tweak_error: null });
    }, [updateCell]);

    const setTweakInstruction = useCallback((cellId: string, instruction: string) => {
        updateCell(cellId, { tweak_instruction: instruction });
    }, [updateCell]);

    const submitTweak = useCallback(async (cellId: string) => {
        const current = cellsRef.current;
        const cell = current.find((c) => c.id === cellId);
        if (!cell || cell.cell_type !== 'code') return;
        const instruction = (cell.tweak_instruction ?? '').trim();
        if (!instruction || cell.tweak_status === 'loading') return;

        const cellIndex = current.findIndex((c) => c.id === cellId);
        updateCell(cellId, { tweak_status: 'loading', tweak_error: null });
        // editCell targets a server-side cell INDEX. Unsaved structural edits
        // (insert/move/delete) make the local index diverge from the on-disk
        // notebook, so persist the current cells first; abort + surface an
        // error if the save fails rather than editing the wrong cell.
        if (dirtyRef.current) {
            const saved = await saveNotebook();
            if (!saved) {
                updateCell(cellId, {
                    tweak_status: 'error',
                    tweak_error: 'Could not save the notebook before editing. Try again.',
                });
                addToast('Save failed — cell edit aborted to avoid targeting the wrong cell', 'error');
                return;
            }
        }
        try {
            const result = await AnalysisAPI.editCell(jobId, cellIndex, cell.code, instruction);
            if (result.success) {
                // Replace the code with the rewritten source. Map the server-
                // side output/images into our CellOutput[] so they surface in
                // the same place a kernel Run would write them.
                const newOutputs: CellOutput[] = [];
                if (result.output) {
                    newOutputs.push({ output_type: 'stream', name: 'stdout', text: result.output });
                }
                if (result.images && result.images.length > 0) {
                    result.images.forEach((img: string) => {
                        newOutputs.push({ output_type: 'display_data', data: { 'image/png': img } });
                    });
                }
                updateCell(cellId, {
                    code: result.new_code,
                    outputs: newOutputs,
                    tweak_status: 'success',
                    tweak_error: null,
                });
                markDirty();
                // Auto-close the tweak input after a brief success flash.
                const prev = tweakTimersRef.current.get(cellId);
                if (prev) clearTimeout(prev);
                const t = setTimeout(() => {
                    updateCell(cellId, {
                        tweak_open: false,
                        tweak_instruction: '',
                        tweak_status: 'idle',
                    });
                    tweakTimersRef.current.delete(cellId);
                }, 1500);
                tweakTimersRef.current.set(cellId, t);
            } else {
                updateCell(cellId, {
                    tweak_status: 'error',
                    tweak_error: result.error || 'Edit failed',
                });
            }
        } catch (e) {
            updateCell(cellId, {
                tweak_status: 'error',
                tweak_error: getErrorMessage(e, 'Network error'),
            });
        }
    }, [jobId, updateCell, markDirty, saveNotebook, addToast]);

    // Re-sync cells when the parent supplies a different initial set.
    //  - jobId change                                → always reset
    //  - seed arrives async (was empty, now populated) → seed once
    //  - subsequent prop changes                     → preserve user edits
    const seededRef = useRef(false);
    useEffect(() => {
        // jobId switch resets the seeded marker so the next non-empty seed
        // re-applies cleanly.
        seededRef.current = false;
        // Reset cell + execution state immediately on job change. Previously
        // cells weren't cleared until a non-empty seed arrived, so a failed or
        // empty fetch left the prior job's cells runnable against the NEW
        // job's kernel. Drop back to a single empty cell and clear the
        // execution map until the new job's seed lands.
        setCells([makeCell('# Enter code here\n', 'code')]);
        executionToCellRef.current.clear();
        setRestartPending(false);
        setDirty(false);
        setSaveStatus('idle');
        setSaveError(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [jobId]);
    useEffect(() => {
        const haveSeed =
            (initialNotebookCells?.length ?? 0) > 0 ||
            (initialCells?.length ?? 0) > 0;
        if (!haveSeed || seededRef.current) return;
        setCells(seedToCells(initialCells, initialNotebookCells));
        executionToCellRef.current.clear();
        setDirty(false);
        setSaveStatus('idle');
        setSaveError(null);
        seededRef.current = true;
    }, [initialNotebookCells, initialCells]);

    // Bundle the (now stable) per-cell handlers into one memoised object.
    // CellRow binds these to its own cell.id, so this object is referentially
    // stable across renders and React.memo on CellRow holds — typing in one
    // cell no longer re-renders every other cell's CodeMirror editor.
    const cellHandlers = useMemo<CellHandlers>(() => ({
        onCodeChange: updateCode,
        onRun: runCell,
        onStop: stopCell,
        onMdEdit: (id) => setMdEditing(id, true),
        onMdPreview: (id) => setMdEditing(id, false),
        onTweakOpen: openTweak,
        onTweakClose: closeTweak,
        onTweakChange: setTweakInstruction,
        onTweakSubmit: submitTweak,
        onInsertBefore: insertCellBefore,
        onInsertAfter: insertCellAfter,
        onDelete: deleteCell,
        onMoveUp: moveCellUp,
        onMoveDown: moveCellDown,
        onToggleType: toggleCellType,
        onRunAbove: runAbove,
        onRunBelow: runBelow,
    }), [
        updateCode, runCell, stopCell, setMdEditing, openTweak, closeTweak,
        setTweakInstruction, submitTweak, insertCellBefore, insertCellAfter,
        deleteCell, moveCellUp, moveCellDown, toggleCellType, runAbove, runBelow,
    ]);

    return (
        <div className="flex flex-col h-full min-h-0 bg-[var(--surface-0)]">
            <header className="shrink-0 px-3 py-2 flex items-center gap-2 border-b border-[var(--rule)]">
                <span className="text-[12px] uppercase tracking-[0.04em] text-[var(--text-dim)]">
                    Live notebook
                </span>
                {dirty && (
                    <span className="text-[10px] uppercase tracking-wider text-[var(--warn)] opacity-80" aria-label="Unsaved changes">
                        Unsaved
                    </span>
                )}
                <span className="ml-auto flex items-center gap-1.5">
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={!dirty || saveStatus === 'saving'}
                        className={`flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none bg-transparent cursor-pointer disabled:opacity-40 disabled:cursor-default ${
                            saveStatus === 'error'
                                ? 'text-[var(--bad)] hover:bg-[color-mix(in_srgb,var(--bad)_10%,transparent)]'
                                : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'
                        }`}
                        aria-label={dirty ? 'Save notebook' : 'Notebook saved'}
                        title={saveError ?? (dirty ? 'Save edits to disk' : 'No unsaved changes')}
                    >
                        {saveStatus === 'saving' ? (
                            <Loader2 size={12} className="animate-spin" />
                        ) : saveStatus === 'saved' ? (
                            <Check size={12} className="text-[var(--ok)]" />
                        ) : (
                            <Save size={12} />
                        )}
                        {saveStatus === 'saved' ? 'Saved' : 'Save'}
                    </button>
                    <button
                        type="button"
                        onClick={runAll}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] rounded text-[var(--accent)] hover:bg-[var(--accent-soft)] border-none bg-transparent cursor-pointer"
                        aria-label="Run all cells"
                    >
                        <PlayCircle size={12} />
                        Run all
                    </button>
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
                        isFirst={idx === 0}
                        isLast={idx === cells.length - 1}
                        canDelete={cells.length > 1}
                        handlers={cellHandlers}
                    />
                ))}
            </div>
        </div>
    );
};

/** Stable, cellId-keyed handlers shared by every CellRow. Because the object
 *  and every function on it are referentially stable, CellRow can be wrapped
 *  in React.memo and only re-renders when its own `cell` reference changes. */
interface CellHandlers {
    onCodeChange: (cellId: string, code: string) => void;
    onRun: (cellId: string) => void;
    onStop: () => void;
    onMdEdit: (cellId: string) => void;
    onMdPreview: (cellId: string) => void;
    onTweakOpen: (cellId: string) => void;
    onTweakClose: (cellId: string) => void;
    onTweakChange: (cellId: string, value: string) => void;
    onTweakSubmit: (cellId: string) => void;
    onInsertBefore: (cellId: string, cellType: 'code' | 'markdown') => void;
    onInsertAfter: (cellId: string, cellType: 'code' | 'markdown') => void;
    onDelete: (cellId: string) => void;
    onMoveUp: (cellId: string) => void;
    onMoveDown: (cellId: string) => void;
    onToggleType: (cellId: string) => void;
    onRunAbove: (cellId: string) => void;
    onRunBelow: (cellId: string) => void;
}

interface CellRowProps {
    index: number;
    cell: LiveCell;
    isFirst: boolean;
    isLast: boolean;
    canDelete: boolean;
    handlers: CellHandlers;
}

const CellRow: FC<CellRowProps> = memo(({
    index,
    cell,
    isFirst,
    isLast,
    canDelete,
    handlers,
}) => {
    const id = cell.id;
    const cellType = cell.cell_type;
    // Bind the shared handlers to this row's id. These closures are recreated
    // each render but never leave CellRow, so they don't defeat the memo.
    const onCodeChange = (code: string) => handlers.onCodeChange(id, code);
    const onRun = () => handlers.onRun(id);
    const onStop = handlers.onStop;
    const onMdEdit = () => handlers.onMdEdit(id);
    const onMdPreview = () => handlers.onMdPreview(id);
    const onTweakOpen = () => handlers.onTweakOpen(id);
    const onTweakClose = () => handlers.onTweakClose(id);
    const onTweakChange = (value: string) => handlers.onTweakChange(id, value);
    const onTweakSubmit = () => handlers.onTweakSubmit(id);
    const onInsertBefore = () => handlers.onInsertBefore(id, cellType);
    const onInsertAfter = () => handlers.onInsertAfter(id, cellType);
    const onDelete = () => handlers.onDelete(id);
    const onMoveUp = () => handlers.onMoveUp(id);
    const onMoveDown = () => handlers.onMoveDown(id);
    const onToggleType = () => handlers.onToggleType(id);
    const onRunAbove = () => handlers.onRunAbove(id);
    const onRunBelow = () => handlers.onRunBelow(id);

    const isCode = cell.cell_type === 'code';
    const isBusy = cell.state === 'busy' || cell.state === 'queued';
    const isError = cell.state === 'error';
    const tweakStatus = cell.tweak_status ?? 'idle';

    const stateColor =
        cell.state === 'busy'
            ? 'var(--accent)'
            : cell.state === 'queued'
            ? 'var(--text-dim)'
            : isError
            ? 'var(--bad)'
            : 'var(--ok)';

    const handleTweakKey = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onTweakSubmit();
        }
        if (e.key === 'Escape') {
            onTweakClose();
        }
    };

    // Shift+Enter and Ctrl/Cmd+Enter both run the cell. Shift+Enter is the
    // Jupyter convention; Ctrl/Cmd+Enter is "run in place" — for now we use
    // the same handler (focus advancement is deferred until we model the
    // Jupyter modal command/edit mode).
    const handleSourceKey = (e: React.KeyboardEvent) => {
        const runShortcut =
            (e.key === 'Enter' && e.shiftKey) ||
            (e.key === 'Enter' && (e.ctrlKey || e.metaKey));
        if (runShortcut) {
            e.preventDefault();
            onRun();
        }
    };

    // -------------------------------------------------------------------
    // Toolbar pieces — Run/Stop or Render (top-of-cell action), Tweak,
    // and the cell-ops cluster (move/insert/delete/toggle/run-above/below).
    // -------------------------------------------------------------------

    const primaryAction = isCode ? (
        isBusy ? (
            <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[rgba(248,113,113,0.1)] text-[var(--bad)] border border-[rgba(248,113,113,0.3)] cursor-pointer"
                aria-label="Stop cell"
            >
                <StopCircle size={11} />
                Stop
            </button>
        ) : (
            <button
                type="button"
                onClick={onRun}
                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[rgba(76,201,240,0.1)] text-[var(--accent)] border border-[rgba(76,201,240,0.3)] cursor-pointer"
                aria-label="Run cell"
            >
                <Play size={11} />
                Run
            </button>
        )
    ) : (
        cell.md_editing && (
            <button
                type="button"
                onClick={onMdPreview}
                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[rgba(76,201,240,0.1)] text-[var(--accent)] border border-[rgba(76,201,240,0.3)] cursor-pointer"
                aria-label="Preview markdown"
            >
                <Play size={11} />
                Render
            </button>
        )
    );

    const cellOps = (
        <div className="flex items-center gap-1 text-[var(--text-dim)]">
            <button
                type="button"
                onClick={onMoveUp}
                disabled={isFirst}
                className="p-1 rounded hover:bg-[rgba(255,255,255,0.05)] disabled:opacity-30 disabled:cursor-not-allowed border-none bg-transparent cursor-pointer"
                aria-label="Move cell up"
                title="Move up"
            >
                <ArrowUp size={12} />
            </button>
            <button
                type="button"
                onClick={onMoveDown}
                disabled={isLast}
                className="p-1 rounded hover:bg-[rgba(255,255,255,0.05)] disabled:opacity-30 disabled:cursor-not-allowed border-none bg-transparent cursor-pointer"
                aria-label="Move cell down"
                title="Move down"
            >
                <ArrowDown size={12} />
            </button>
            <span className="mx-1 h-3 border-l border-[var(--rule)]" />
            <button
                type="button"
                onClick={onInsertBefore}
                className="p-1 rounded hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer"
                aria-label="Insert cell above"
                title="Insert cell above"
            >
                <Plus size={12} className="rotate-180" />
            </button>
            <button
                type="button"
                onClick={onInsertAfter}
                className="p-1 rounded hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer"
                aria-label="Insert cell below"
                title="Insert cell below"
            >
                <Plus size={12} />
            </button>
            <button
                type="button"
                onClick={onToggleType}
                className="p-1 rounded hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer"
                aria-label={isCode ? 'Convert to markdown' : 'Convert to code'}
                title={isCode ? 'Convert to markdown' : 'Convert to code'}
            >
                {isCode ? <FileText size={12} /> : <CodeIcon size={12} />}
            </button>
            <span className="mx-1 h-3 border-l border-[var(--rule)]" />
            {isCode && (
                <>
                    <button
                        type="button"
                        onClick={onRunAbove}
                        disabled={isFirst}
                        className="p-1 rounded hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] disabled:opacity-30 disabled:cursor-not-allowed border-none bg-transparent cursor-pointer"
                        aria-label="Run cells above"
                        title="Run all cells above"
                    >
                        <PlayCircle size={12} className="-scale-y-100" />
                    </button>
                    <button
                        type="button"
                        onClick={onRunBelow}
                        className="p-1 rounded hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] border-none bg-transparent cursor-pointer"
                        aria-label="Run cells below"
                        title="Run this cell and below"
                    >
                        <PlayCircle size={12} />
                    </button>
                    <span className="mx-1 h-3 border-l border-[var(--rule)]" />
                </>
            )}
            <button
                type="button"
                onClick={onDelete}
                disabled={!canDelete}
                className="p-1 rounded hover:bg-[color-mix(in_srgb,var(--bad)_15%,transparent)] hover:text-[var(--bad)] disabled:opacity-30 disabled:cursor-not-allowed border-none bg-transparent cursor-pointer"
                aria-label="Delete cell"
                title="Delete cell"
            >
                <Trash2 size={12} />
            </button>
        </div>
    );

    return (
        <article className="border-b border-[var(--rule)] last:border-b-0">
            <div className="flex items-stretch">
                {/* Gutter — execution count + state dot (code cells); type
                    label "Md" for markdown so the row is identifiable at a
                    glance. */}
                <div className="shrink-0 w-12 flex flex-col items-center pt-2 pb-1.5 gap-1">
                    {isCode ? (
                        <>
                            <span
                                className={`inline-block w-1.5 h-1.5 rounded-full ${
                                    isBusy ? 'animate-pulse' : ''
                                }`}
                                style={{ backgroundColor: stateColor }}
                                aria-label={`Cell ${index + 1} ${cell.state}`}
                            />
                            <span className="font-mono text-[12px] text-[var(--text-dim)]">
                                [{cell.execution_count ?? ' '}]
                            </span>
                        </>
                    ) : (
                        <span className="font-mono text-[11px] text-[var(--text-dim)] uppercase tracking-wider mt-1">
                            Md
                        </span>
                    )}
                </div>

                {/* Body — toolbar on top, source/preview below. Execution
                    time + killed-reason live below the outputs (out-of-body). */}
                <div className="flex-1 min-w-0 py-2 pr-2">
                    {/* TOP toolbar: primary action (Run/Stop or Render) +
                        Tweak (code cells) + cell ops. */}
                    <div className="flex items-center gap-1 mb-1.5">
                        {primaryAction}
                        {isCode && !cell.tweak_open && (
                            <button
                                type="button"
                                onClick={onTweakOpen}
                                className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded text-[var(--text-secondary)] border border-dashed border-[var(--rule)] bg-transparent cursor-pointer hover:bg-[var(--accent-soft)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                                aria-label="Tweak cell with AI"
                            >
                                <Sparkles size={11} />
                                Tweak
                            </button>
                        )}
                        <span className="ml-auto" />
                        {cellOps}
                    </div>

                    {/* Tweak input (code cells only, when open). */}
                    {isCode && cell.tweak_open && (
                        <div className="mb-1.5 flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--accent)] rounded-md px-2.5 py-1.5">
                            <Sparkles size={14} className="text-[var(--accent)] shrink-0" />
                            <input
                                type="text"
                                autoFocus
                                className="flex-1 bg-transparent border-none outline-none text-[var(--text-primary)] text-[0.85rem] font-sans placeholder:text-[var(--text-secondary)] placeholder:opacity-60"
                                placeholder={`e.g. "Use a vibrant palette and add a title"`}
                                value={cell.tweak_instruction ?? ''}
                                onChange={(e) => onTweakChange(e.target.value)}
                                onKeyDown={handleTweakKey}
                                disabled={tweakStatus === 'loading'}
                                aria-label={`Tweak instruction for cell ${index + 1}`}
                            />
                            {tweakStatus === 'loading' && (
                                <Loader2 size={14} className="animate-spin text-[var(--accent)]" />
                            )}
                            {tweakStatus === 'success' && (
                                <Check size={14} className="text-[var(--ok)]" />
                            )}
                            {tweakStatus === 'error' && (
                                <span className="flex items-center gap-1 text-[0.75rem] text-[var(--bad)] whitespace-nowrap">
                                    <AlertTriangle size={12} />
                                    {cell.tweak_error}
                                </span>
                            )}
                        </div>
                    )}

                    {/* Source — code editor, markdown editor, or markdown preview. */}
                    {isCode ? (
                        <CellSourceEditor
                            value={cell.code}
                            onChange={onCodeChange}
                            onKeyDown={handleSourceKey}
                            language="python"
                            ariaLabel={`Cell ${index + 1} source`}
                        />
                    ) : cell.md_editing ? (
                        <CellSourceEditor
                            value={cell.code}
                            onChange={onCodeChange}
                            onKeyDown={handleSourceKey}
                            language="markdown"
                            ariaLabel={`Markdown cell ${index + 1} source`}
                        />
                    ) : (
                        <button
                            type="button"
                            onClick={onMdEdit}
                            className="block w-full text-left bg-transparent border border-transparent rounded p-1 -m-1 hover:border-[var(--rule)] focus-visible:border-[var(--accent)] focus-visible:outline-none cursor-text"
                            aria-label={`Edit markdown cell ${index + 1}`}
                        >
                            <div
                                className="text-[var(--text-primary)] leading-[1.65] text-[0.9rem] [&_h1]:text-[1.4rem] [&_h1]:my-2 [&_h1]:text-[var(--text-primary)] [&_h2]:text-[1.2rem] [&_h2]:my-1.5 [&_h2]:text-[var(--text-primary)] [&_h3]:text-base [&_h3]:my-1 [&_h3]:text-[var(--text-primary)] [&_code]:bg-white/[0.04] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-sm [&_code]:text-[0.85em]"
                                dangerouslySetInnerHTML={{ __html: formatMarkdown(cell.code) }}
                            />
                            <span className="inline-flex items-center gap-1 mt-1 text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
                                <Pencil size={10} />
                                Click to edit
                            </span>
                        </button>
                    )}
                </div>
            </div>

            {/* Outputs */}
            {cell.outputs.length > 0 && (
                <div className="ml-12 mr-2 mb-2 border-l-2 border-[var(--rule)]">
                    {cell.outputs.map((output, i) => (
                        <CellOutputView key={i} output={output} />
                    ))}
                </div>
            )}

            {/* BOTTOM: execution time + killed reason (code cells only). */}
            {isCode && (cell.duration_ms != null || cell.killed_reason) && cell.state !== 'busy' && (
                <div className="ml-12 mr-2 pb-2 flex items-center gap-3 font-mono text-[11px] text-[var(--text-dim)]">
                    {cell.duration_ms != null && (
                        <span>{cell.duration_ms} ms</span>
                    )}
                    {cell.killed_reason && (
                        <span className="text-[var(--warn)]">killed: {cell.killed_reason}</span>
                    )}
                </div>
            )}
        </article>
    );
});
CellRow.displayName = 'CellRow';
