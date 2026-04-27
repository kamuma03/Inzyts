import { type FC } from 'react';
import { Sparkline } from './primitives/Sparkline';
import { formatTokens, formatCost } from '../../utils/formatters';
import type { RunMetricsHistory } from '../../hooks/useRunMetrics';

interface TrafficRowProps {
    history: RunMetricsHistory;
}

const last = (arr: number[]): number => (arr.length > 0 ? arr[arr.length - 1] : 0);

/** Three compact sparklines: token rate / cumulative tokens / cumulative cost.
 *  Sourced from the rolling 60-point history maintained by useRunMetrics. */
export const TrafficRow: FC<TrafficRowProps> = ({ history }) => (
    <div className="grid grid-cols-3 gap-3 px-3 py-2 border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)]">
        <Cell label="tok/s" value={`${last(history.tokenRate).toFixed(1)}`} values={history.tokenRate} />
        <Cell label="tokens" value={formatTokens(last(history.tokens))} values={history.tokens} />
        <Cell label="cost" value={formatCost(last(history.cost))} values={history.cost} />
    </div>
);

interface CellProps {
    label: string;
    value: string;
    values: number[];
}

const Cell: FC<CellProps> = ({ label, value, values }) => (
    <div className="flex items-center gap-2">
        <div className="flex flex-col gap-0.5 min-w-0">
            <span className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">{value}</span>
            <span className="text-[9px] uppercase tracking-[1.5px] text-[var(--text-dim)]">{label}</span>
        </div>
        <Sparkline values={values} width={80} height={20} ariaLabel={`${label} trend`} />
    </div>
);
