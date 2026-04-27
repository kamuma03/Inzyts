import type { FC } from 'react';
import type { ColumnProfile } from '../../api';
import { formatTokens } from '../../utils/formatters';
import { roleVar, dtypeVar } from '../../utils/colorScales';
import { MiniBars } from './primitives/MiniBars';

interface ColumnDetailCardProps {
    column: ColumnProfile | null;
}

const formatStat = (n: number | null | undefined): string => {
    if (n == null || !Number.isFinite(n)) return '—';
    if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
    if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
    if (Math.abs(n) < 0.01 && n !== 0) return n.toExponential(1);
    return Number.isInteger(n) ? `${n}` : n.toFixed(2);
};

/** Detail panel for the currently selected column in the inspector. */
export const ColumnDetailCard: FC<ColumnDetailCardProps> = ({ column }) => {
    if (!column) {
        return (
            <div className="p-3 border border-dashed border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)] text-center text-[12px] text-[var(--text-dim)]">
                Select a column to inspect its profile.
            </div>
        );
    }

    return (
        <div className="p-3 border border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)]">
            <div className="flex items-center gap-2 mb-2">
                <h3
                    className="m-0 font-mono text-[13px] font-semibold text-[var(--text-primary)] truncate"
                    title={column.name}
                >
                    {column.name}
                </h3>
                <span
                    className="ml-auto px-1.5 py-0.5 text-[9px] uppercase tracking-[1px] rounded shrink-0"
                    style={{
                        color: roleVar(column.role),
                        backgroundColor: 'rgba(255,255,255,0.05)',
                    }}
                >
                    {column.role}
                </span>
            </div>

            <div className="flex items-center gap-2 mb-3 text-[11px] text-[var(--text-dim)]">
                <span style={{ color: dtypeVar(column.dtype) }}>{column.dtype}</span>
                <span>·</span>
                <span className="font-mono">{column.cardinality_or_range}</span>
                <span>·</span>
                <span>{column.null_count > 0 ? `${formatTokens(column.null_count)} nulls` : 'no nulls'}</span>
            </div>

            {column.histogram && column.histogram.length > 0 && (
                <div className="mb-3">
                    <MiniBars
                        values={column.histogram}
                        width={240}
                        height={36}
                        color={dtypeVar(column.dtype)}
                        ariaLabel={`distribution of ${column.name}`}
                    />
                </div>
            )}

            {column.stats && (
                <dl className="m-0 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                    <Stat label="mean" value={formatStat(column.stats.mean)} />
                    <Stat label="median" value={formatStat(column.stats.median)} />
                    <Stat label="min" value={formatStat(column.stats.min)} />
                    <Stat label="max" value={formatStat(column.stats.max)} />
                    {column.stats.p99 != null && (
                        <Stat label="p99" value={formatStat(column.stats.p99)} />
                    )}
                </dl>
            )}
        </div>
    );
};

const Stat: FC<{ label: string; value: string }> = ({ label, value }) => (
    <div className="flex items-baseline gap-1.5">
        <dt className="m-0 uppercase tracking-[1px] text-[var(--text-dim)]">{label}</dt>
        <dd className="m-0 font-mono text-[var(--text-primary)]">{value}</dd>
    </div>
);
