import { memo, useMemo, type FC } from 'react';
import { X, Download } from 'lucide-react';
import type { JobSummary, RunMetrics } from '../../api';
import {
    formatCost,
    formatDuration,
    formatTokens,
    formatDelta,
    type DeltaResult,
} from '../../utils/formatters';

interface TopStripProps {
    job: JobSummary;
    metrics: RunMetrics | null;
    onCancel?: () => void;
    onExport?: () => void;
}

const directionClass: Record<DeltaResult['direction'], string> = {
    better: 'text-[var(--status-good)]',
    worse: 'text-[var(--status-warn)]',
    same: 'text-[var(--text-dim)]',
    none: 'hidden',
};

interface KpiCellProps {
    label: string;
    value: string;
    delta?: DeltaResult | null;
}

const KpiCell: FC<KpiCellProps> = memo(({ label, value, delta }) => (
    <div className="flex flex-col gap-0.5">
        <div className="flex items-baseline gap-1.5">
            <span className="font-mono font-semibold text-[15px] text-[var(--text-primary)]">{value}</span>
            {delta && delta.direction !== 'none' && (
                <span className={`font-mono text-[10px] ${directionClass[delta.direction]}`}>
                    {delta.label}
                </span>
            )}
        </div>
        <span className="text-[9px] uppercase tracking-[1.5px] text-[var(--text-dim)]">{label}</span>
    </div>
));

KpiCell.displayName = 'KpiCell';

export const TopStrip: FC<TopStripProps> = ({ job, metrics, onCancel, onExport }) => {
    const filename = (job.csv_path?.split('/').pop()) || 'untitled';
    const isRunning = job.status === 'running' || job.status === 'pending';

    const previous = metrics?.previous ?? null;
    const elapsed = metrics?.elapsed_seconds ?? null;
    const eta = metrics?.eta_seconds ?? null;
    const tokens = metrics?.tokens_used ?? job.token_usage?.total ?? null;
    const cost = metrics?.cost_usd ?? job.cost_estimate?.total ?? job.cost_estimate?.estimated_cost_usd ?? null;
    const agentsActive = metrics?.agents_active ?? null;
    const agentsTotal = metrics?.agents_total ?? null;

    // Memoise deltas so KpiCell.memo can skip re-renders when only the parent
    // re-renders without the underlying numbers changing (every 500ms metric tick).
    const elapsedDelta = useMemo(
        () =>
            previous
                ? formatDelta(elapsed ?? null, previous.elapsed_seconds ?? null, {
                      lowerIsBetter: true,
                      formatter: (n) => formatDuration(n),
                  })
                : null,
        [elapsed, previous],
    );
    const tokensDelta = useMemo(
        () =>
            previous
                ? formatDelta(tokens ?? null, previous.tokens_used ?? null, {
                      lowerIsBetter: true,
                      formatter: (n) => formatTokens(n),
                  })
                : null,
        [tokens, previous],
    );
    const costDelta = useMemo(
        () =>
            previous
                ? formatDelta(cost ?? null, previous.cost_usd ?? null, {
                      lowerIsBetter: true,
                      formatter: (n) => formatCost(n).replace('$', ''),
                      unit: '',
                  })
                : null,
        [cost, previous],
    );

    return (
        <div className="border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)]">
            {/* Identity row */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-[var(--border-color)]">
                <span className="font-mono text-[13px] font-semibold text-[var(--text-primary)] truncate">
                    {filename}
                </span>
                <span className="font-mono text-[10px] text-[var(--text-dim)]">
                    job_id={job.id.slice(0, 8)}
                </span>
                <span
                    className="px-1.5 py-0.5 text-[9px] uppercase tracking-[1px] rounded bg-[rgba(76,201,240,0.12)] text-[var(--bg-turquoise-surf)]"
                    aria-label={`Analysis mode: ${job.mode}`}
                >
                    {job.mode}
                </span>
                {metrics?.previous_job_id && (
                    <span className="text-[10px] text-[var(--text-dim)]">
                        vs.{' '}
                        <a
                            href={`/jobs/${metrics.previous_job_id}`}
                            className="font-mono text-[var(--bg-blue-green)] hover:underline"
                        >
                            {metrics.previous_job_id.slice(0, 8)}
                        </a>
                    </span>
                )}

                <div className="ml-auto flex items-center gap-2">
                    <span className="text-[10px] text-[var(--text-dim)]">
                        <kbd className="font-mono px-1 bg-[rgba(255,255,255,0.05)] rounded">⌘K</kbd>
                    </span>
                    {isRunning && onCancel && (
                        <button
                            type="button"
                            onClick={onCancel}
                            className="flex items-center gap-1 px-2 py-1 text-[11px] rounded bg-[rgba(248,113,113,0.1)] text-[var(--status-bad)] border border-[rgba(248,113,113,0.3)] hover:bg-[rgba(248,113,113,0.2)] transition-colors"
                            aria-label="Cancel job"
                        >
                            <X size={12} />
                            <span>Cancel</span>
                        </button>
                    )}
                    {!isRunning && onExport && (
                        <button
                            type="button"
                            onClick={onExport}
                            className="flex items-center gap-1 px-2 py-1 text-[11px] rounded bg-[rgba(76,201,240,0.1)] text-[var(--bg-turquoise-surf)] border border-[rgba(76,201,240,0.3)] hover:bg-[rgba(76,201,240,0.2)] transition-colors"
                            aria-label="Export"
                        >
                            <Download size={12} />
                            <span>Export</span>
                        </button>
                    )}
                </div>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-6 gap-4 px-4 py-3">
                <KpiCell label="elapsed" value={elapsed != null ? formatDuration(elapsed) : '—'} delta={elapsedDelta} />
                <KpiCell label="eta" value={eta != null ? formatDuration(eta) : '—'} />
                <KpiCell label="tokens" value={formatTokens(tokens)} delta={tokensDelta} />
                <KpiCell label="cost" value={formatCost(cost)} delta={costDelta} />
                <KpiCell
                    label="quality"
                    value={metrics?.quality_score != null ? metrics.quality_score.toFixed(2) : '—'}
                />
                <KpiCell
                    label="agents"
                    value={
                        agentsActive != null && agentsTotal != null
                            ? `${agentsActive}/${agentsTotal}`
                            : '—'
                    }
                />
            </div>
        </div>
    );
};
