import { useMemo, type FC } from 'react';
import { X, Cpu, Variable, DollarSign, RefreshCw, Loader2 } from 'lucide-react';
import type { RunMetrics, KernelVariable } from '../../../../api';
import type { LiveCell } from './types';

export type KernelStatus = 'idle' | 'busy' | 'restarting';

interface KernelInspectorProps {
    cells: LiveCell[];
    /** Live kernel namespace from the introspection endpoint. */
    variables: KernelVariable[];
    /** False until a kernel session exists (no cell has been run yet). */
    kernelActive: boolean;
    variablesLoading: boolean;
    onRefresh: () => void;
    metrics: RunMetrics | null;
    kernelStatus: KernelStatus;
    onClose: () => void;
}

interface InferredVar {
    name: string;
    kind: 'variable' | 'function' | 'class' | 'import';
}

/** Best-effort static scan of the cell sources for top-level names. Used as a
 *  fallback for the Variables list before the kernel is live (no session yet),
 *  and shared with the editor's autocomplete source (FR-7). */
export function inferVariables(cells: LiveCell[]): InferredVar[] {
    const found = new Map<string, InferredVar>();
    const add = (name: string, kind: InferredVar['kind']) => {
        if (!name || name === '_') return;
        if (!found.has(name)) found.set(name, { name, kind });
    };
    for (const cell of cells) {
        if (cell.cell_type !== 'code') continue;
        for (const raw of cell.code.split('\n')) {
            const line = raw.replace(/\t/g, '    ');
            if (/^\s/.test(raw)) continue; // top-level only (no leading indent)
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;

            let m: RegExpMatchArray | null;
            if ((m = trimmed.match(/^def\s+([A-Za-z_]\w*)/))) { add(m[1], 'function'); continue; }
            if ((m = trimmed.match(/^class\s+([A-Za-z_]\w*)/))) { add(m[1], 'class'); continue; }
            if ((m = trimmed.match(/^import\s+([A-Za-z_]\w*)(?:\s+as\s+([A-Za-z_]\w*))?/))) {
                add(m[2] || m[1], 'import'); continue;
            }
            if ((m = trimmed.match(/^from\s+[\w.]+\s+import\s+(.+)/))) {
                m[1].split(',').forEach((part) => {
                    const name = part.trim().split(/\s+as\s+/).pop()?.trim();
                    if (name && name !== '*') add(name, 'import');
                });
                continue;
            }
            // Assignment: `a = ...`, `a: int = ...`, `a, b = ...` (skip ==, <=).
            if ((m = trimmed.match(/^([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?::[^=]+)?=(?!=)/))) {
                m[1].split(',').forEach((n) => add(n.trim(), 'variable'));
            }
        }
    }
    return [...found.values()];
}

const INFERRED_KIND_COLOR: Record<InferredVar['kind'], string> = {
    variable: 'var(--accent)',
    function: 'var(--accent-violet)',
    class: 'var(--ok)',
    import: 'var(--text-dim)',
};

const LIVE_KIND_COLOR: Record<KernelVariable['kind'], string> = {
    value: 'var(--accent)',
    callable: 'var(--accent-violet)',
    module: 'var(--text-dim)',
};

/** Compact type annotation: `DataFrame (100×5)`, `list (3)`, or just the type. */
function shapeLabel(v: KernelVariable): string {
    if (v.shape && v.shape.length) return `${v.type_name} (${v.shape.join('×')})`;
    if (v.length != null) return `${v.type_name} (${v.length})`;
    return v.type_name;
}

const Section: FC<{ icon: React.ReactNode; title: string; action?: React.ReactNode; children: React.ReactNode }> = ({
    icon, title, action, children,
}) => (
    <section className="px-3 py-2.5 border-b border-[var(--rule)]">
        <h4 className="flex items-center gap-1.5 m-0 mb-2 text-[10px] uppercase tracking-[0.1em] text-[var(--text-dim)] font-mono">
            {icon}
            {title}
            {action && <span className="ml-auto">{action}</span>}
        </h4>
        {children}
    </section>
);

const Stat: FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone }) => (
    <div className="flex items-center justify-between py-0.5 text-[12px]">
        <span className="text-[var(--text-secondary)]">{label}</span>
        <span className="font-mono" style={{ color: tone ?? 'var(--text-primary)' }}>{value}</span>
    </div>
);

/** Collapsible right-hand panel for Workspace mode: kernel session state, live
 *  variables (name / type / shape / preview), and Tweak cost telemetry
 *  (FR-10). Read-only — it never forks the cell/exec model. */
export const KernelInspector: FC<KernelInspectorProps> = ({
    cells, variables, kernelActive, variablesLoading, onRefresh, metrics, kernelStatus, onClose,
}) => {
    const inferred = useMemo(() => inferVariables(cells), [cells]);
    // Live introspection includes imported modules (pd/np/…); those clutter the
    // panel, so show only values + callables and surface module count instead.
    const liveVars = useMemo(
        () => variables.filter((v) => v.kind !== 'module'),
        [variables],
    );
    const cellsRun = useMemo(
        () => cells.filter((c) => c.cell_type === 'code' && c.execution_count != null).length,
        [cells],
    );

    const statusTone =
        kernelStatus === 'busy' ? 'var(--accent)'
        : kernelStatus === 'restarting' ? 'var(--warn)'
        : 'var(--ok)';

    const cost = metrics?.cost_usd ?? null;
    const tokens = metrics?.tokens_used ?? null;
    const showLive = kernelActive && liveVars.length > 0;
    const varCount = showLive ? liveVars.length : inferred.length;

    return (
        <aside
            className="kernel-inspector flex flex-col h-full w-[280px] shrink-0 bg-[var(--surface-1)] border-l border-[var(--rule)]"
            aria-label="Kernel inspector"
        >
            <header className="shrink-0 flex items-center px-3 py-2 border-b border-[var(--rule)]">
                <span className="text-[11px] uppercase tracking-[0.1em] text-[var(--text-secondary)] font-mono">
                    Kernel Inspector
                </span>
                <button
                    type="button"
                    onClick={onClose}
                    className="ml-auto p-1 rounded text-[var(--text-dim)] hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer"
                    aria-label="Close inspector"
                    title="Close inspector"
                >
                    <X size={14} />
                </button>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto">
                <Section icon={<Cpu size={11} />} title="Session">
                    <div className="flex items-center gap-1.5 mb-1.5">
                        <span
                            className={`inline-block w-1.5 h-1.5 rounded-full ${kernelStatus === 'busy' ? 'animate-pulse' : ''}`}
                            style={{ backgroundColor: statusTone }}
                        />
                        <span className="text-[12px] font-mono" style={{ color: statusTone }}>
                            python3 · {kernelActive ? kernelStatus : 'not started'}
                        </span>
                    </div>
                    <Stat label="Cells run" value={String(cellsRun)} />
                    <Stat label="Cells total" value={String(cells.length)} />
                </Section>

                <Section
                    icon={<Variable size={11} />}
                    title={`Variables · ${varCount}`}
                    action={
                        <button
                            type="button"
                            onClick={onRefresh}
                            disabled={variablesLoading}
                            className="p-0.5 rounded text-[var(--text-dim)] hover:text-[var(--accent)] hover:bg-[rgba(255,255,255,0.05)] border-none bg-transparent cursor-pointer disabled:opacity-50"
                            aria-label="Refresh variables"
                            title="Refresh from kernel"
                        >
                            {variablesLoading
                                ? <Loader2 size={11} className="animate-spin" />
                                : <RefreshCw size={11} />}
                        </button>
                    }
                >
                    {varCount === 0 ? (
                        <p className="m-0 text-[11px] text-[var(--text-dim)] italic">
                            {kernelActive ? 'No user variables yet.' : 'Run a cell to start the kernel.'}
                        </p>
                    ) : showLive ? (
                        <ul className="m-0 p-0 list-none flex flex-col gap-1">
                            {liveVars.map((v) => (
                                <li key={v.name} className="flex flex-col gap-0.5">
                                    <div className="flex items-center gap-2 text-[12px] font-mono">
                                        <span
                                            className="inline-block w-1 h-1 rounded-full shrink-0"
                                            style={{ backgroundColor: LIVE_KIND_COLOR[v.kind] }}
                                        />
                                        <span className="text-[var(--text-primary)] truncate">{v.name}</span>
                                        <span className="ml-auto text-[10px] text-[var(--text-dim)] truncate max-w-[120px]" title={shapeLabel(v)}>
                                            {shapeLabel(v)}
                                        </span>
                                    </div>
                                    {v.preview && (
                                        <span className="pl-3 text-[10px] text-[var(--text-dim)] font-mono truncate" title={v.preview}>
                                            {v.preview}
                                        </span>
                                    )}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <>
                            <ul className="m-0 p-0 list-none flex flex-col gap-0.5">
                                {inferred.map((v) => (
                                    <li key={v.name} className="flex items-center gap-2 text-[12px] font-mono">
                                        <span
                                            className="inline-block w-1 h-1 rounded-full shrink-0"
                                            style={{ backgroundColor: INFERRED_KIND_COLOR[v.kind] }}
                                        />
                                        <span className="text-[var(--text-primary)] truncate">{v.name}</span>
                                        <span className="ml-auto text-[10px] text-[var(--text-dim)]">{v.kind}</span>
                                    </li>
                                ))}
                            </ul>
                            <p className="m-0 mt-2 text-[10px] text-[var(--text-dim)] italic leading-snug">
                                Inferred from source — run a cell for live kernel values.
                            </p>
                        </>
                    )}
                </Section>

                <Section icon={<DollarSign size={11} />} title="Cost">
                    <Stat
                        label="Session cost"
                        value={cost != null ? `$${cost.toFixed(4)}` : '—'}
                        tone="var(--accent)"
                    />
                    <Stat
                        label="Tokens"
                        value={tokens != null ? tokens.toLocaleString() : '—'}
                    />
                </Section>
            </div>
        </aside>
    );
};
