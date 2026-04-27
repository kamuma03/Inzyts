import { useEffect, useState, type FC } from 'react';
import { CommandCenterAPI, type CostBreakdownResponse } from '../../api';
import { formatCost } from '../../utils/formatters';
import { Donut } from './primitives/Donut';
import { DollarSign } from 'lucide-react';

interface CostBreakdownProps {
    jobId: string;
    /** Re-fetch when this changes (e.g. job status flipped to completed). */
    refreshKey?: string | number;
}

const PHASE_COLORS: Record<string, string> = {
    phase1: 'var(--bg-blue-green)',
    extensions: 'var(--accent-violet)',
    phase2: 'var(--bg-turquoise-surf)',
    all: 'var(--text-secondary)',
};

export const CostBreakdown: FC<CostBreakdownProps> = ({ jobId, refreshKey }) => {
    const [data, setData] = useState<CostBreakdownResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!jobId) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        CommandCenterAPI.getCost(jobId)
            .then((d) => {
                if (cancelled) return;
                setData(d);
                setLoading(false);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err?.message ?? 'Failed to load cost breakdown');
                setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [jobId, refreshKey]);

    return (
        <div className="p-3 border border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)]">
            <div className="flex items-center gap-2 mb-3 text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                <DollarSign size={12} />
                <span>Cost</span>
                {data?.is_estimate && (
                    <span className="ml-auto px-1.5 py-px text-[9px] rounded bg-[rgba(251,191,36,0.15)] text-[var(--status-warn)]">
                        ESTIMATE
                    </span>
                )}
            </div>

            {loading && <div className="text-[12px] text-[var(--text-dim)]">Loading…</div>}
            {error && <div className="text-[12px] text-[var(--status-bad)]">{error}</div>}

            {data && !loading && (
                <>
                    <div className="flex items-center gap-3 mb-3">
                        <Donut
                            slices={data.rows.map((r) => ({
                                label: r.label,
                                value: r.cost_usd,
                                color: PHASE_COLORS[r.phase] ?? 'var(--text-secondary)',
                            }))}
                            size={64}
                            thickness={10}
                            ariaLabel={`cost breakdown totalling ${formatCost(data.total_cost_usd)}`}
                        />
                        <div className="flex-1">
                            <div className="text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">Total</div>
                            <div className="text-[18px] font-mono font-semibold text-[var(--text-primary)]">
                                {formatCost(data.total_cost_usd)}
                            </div>
                        </div>
                    </div>

                    <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
                        {data.rows.map((row) => (
                            <li
                                key={row.phase}
                                className="flex items-center gap-2 text-[12px]"
                            >
                                <span
                                    className="inline-block w-2 h-2 rounded-full shrink-0"
                                    style={{ backgroundColor: PHASE_COLORS[row.phase] ?? 'var(--text-secondary)' }}
                                />
                                <span className="text-[var(--text-secondary)] flex-1 truncate">
                                    {row.label}
                                </span>
                                <span className="font-mono text-[var(--text-primary)]">
                                    {formatCost(row.cost_usd)}
                                </span>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
};
