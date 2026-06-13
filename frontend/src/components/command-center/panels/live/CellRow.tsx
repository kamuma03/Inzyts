import { memo, type FC } from 'react';
import { Play, StopCircle, Plus, Loader2, Sparkles, Check, AlertTriangle, Pencil, ArrowUp, ArrowDown, Trash2, Code as CodeIcon, FileText, PlayCircle } from 'lucide-react';
import { formatMarkdown } from '../../../../utils/formatMarkdown';
import { CellOutputView } from './outputs/CellOutputView';
import { CellSourceEditor } from './CellSourceEditor';
import { errorLineFromTraceback } from './pythonEditorSupport';
import type { LiveCell } from './types';

/** Stable, cellId-keyed handlers shared by every CellRow. Because the object
 *  and every function on it are referentially stable, CellRow can be wrapped
 *  in React.memo and only re-renders when its own `cell` reference changes. */
export interface CellHandlers {
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

export const CellRow: FC<CellRowProps> = memo(({
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

    // Derive the error line (FR-8) from this cell's own error output. Cheap and
    // local — recomputed only when the memoised `cell` reference changes.
    const errorOutput = cell.outputs.find((o) => o.output_type === 'error');
    const errorLine =
        isError && errorOutput?.output_type === 'error'
            ? errorLineFromTraceback(errorOutput.traceback)
            : null;

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
                            cellId={id}
                            errorLine={errorLine}
                        />
                    ) : cell.md_editing ? (
                        <CellSourceEditor
                            value={cell.code}
                            onChange={onCodeChange}
                            onKeyDown={handleSourceKey}
                            language="markdown"
                            ariaLabel={`Markdown cell ${index + 1} source`}
                            cellId={id}
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
