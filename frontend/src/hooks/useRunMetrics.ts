import { useEffect, useRef, useState } from 'react';
import { useSocket } from './useSocket';
import type { RunMetrics } from '../api';

export interface RunMetricsHistory {
    /** Tokens-per-second (derived from successive tokens_used deltas). */
    tokenRate: number[];
    /** Cumulative tokens_used at each tick. */
    tokens: number[];
    /** Cumulative cost_usd at each tick. */
    cost: number[];
}

const HISTORY_LIMIT = 60;
const EMPTY_HISTORY: RunMetricsHistory = { tokenRate: [], tokens: [], cost: [] };

const pushBounded = (arr: number[], v: number, max = HISTORY_LIMIT): number[] => {
    const next = arr.length >= max ? arr.slice(1) : arr.slice();
    next.push(v);
    return next;
};

/** Subscribes to ``metrics_snapshot`` and returns the latest payload. */
export const useRunMetrics = (jobId: string | null): RunMetrics | null => {
    const { metrics } = useSocket(jobId);
    return metrics;
};

/** Maintains a rolling 60-point history derived from successive metrics
 *  pushes. Pass ``metrics`` from any source (useRunMetrics, JobContext, etc.).
 *  Resets when ``resetKey`` changes — typically the active jobId. */
export const useMetricsHistory = (
    metrics: RunMetrics | null,
    resetKey: string | null,
): RunMetricsHistory => {
    const [history, setHistory] = useState<RunMetricsHistory>(EMPTY_HISTORY);
    const lastRef = useRef<{ tokens: number; ts: number } | null>(null);

    useEffect(() => {
        setHistory(EMPTY_HISTORY);
        lastRef.current = null;
    }, [resetKey]);

    useEffect(() => {
        if (!metrics) return;
        const now = Date.now() / 1000;
        const last = lastRef.current;
        const dt = last ? Math.max(0.001, now - last.ts) : 0;
        const dTokens = last ? Math.max(0, metrics.tokens_used - last.tokens) : 0;
        const tokenRate = last && dt > 0 ? dTokens / dt : 0;
        lastRef.current = { tokens: metrics.tokens_used, ts: now };

        setHistory((prev) => ({
            tokenRate: pushBounded(prev.tokenRate, tokenRate),
            tokens: pushBounded(prev.tokens, metrics.tokens_used),
            cost: pushBounded(prev.cost, metrics.cost_usd),
        }));
    }, [metrics]);

    return history;
};
