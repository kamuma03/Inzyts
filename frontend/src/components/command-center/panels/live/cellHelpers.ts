import type { LiveCell, NotebookCellSeed } from './types';

/** Stable, collision-resistant id for a notebook cell row. */
export const newCellId = (): string =>
    `cell-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/** Stable id used to correlate an execution request with its WS event stream. */
export const newExecutionId = (): string =>
    `exec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/** Build a fresh `LiveCell` with all per-cell state zeroed out. */
export const makeCell = (
    source: string,
    cell_type: 'code' | 'markdown' = 'code',
): LiveCell => ({
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

/** Map the parent's seed props into the initial cell stack. The typed
 *  notebook seed wins over the legacy code-only seed; an empty seed falls
 *  back to a single placeholder code cell. */
export const seedToCells = (
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
