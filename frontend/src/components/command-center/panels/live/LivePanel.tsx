import { useCallback, useEffect, useMemo, useRef, useState, type FC } from 'react';
import { Plus, RotateCcw, Loader2, Check, PlayCircle, Save } from 'lucide-react';
import { AnalysisAPI } from '../../../../api';
import { useSocket } from '../../../../hooks/useSocket';
import { getErrorMessage } from '../../../../utils/errorMessage';
import { useJobContext } from '../../../../context/JobContext';
import { CellRow, type CellHandlers } from './CellRow';
import { makeCell, seedToCells } from './cellHelpers';
import { useCellExecution } from './useCellExecution';
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

    // -- Cell execution lifecycle (run / run-many / stop / restart) ---------

    const { runCell, runAll, runAbove, runBelow, stopCell, restartKernel } = useCellExecution({
        jobId,
        cellsRef,
        executionToCellRef,
        updateCell,
        setCells,
        setRestartPending,
    });

    // -- Cell controls ------------------------------------------------------

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
