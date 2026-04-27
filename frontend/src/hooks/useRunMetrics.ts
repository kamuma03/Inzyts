import { useSocket } from './useSocket';
import type { RunMetrics } from '../api';

/** Subscribes to ``metrics_snapshot`` and returns the latest payload. */
export const useRunMetrics = (jobId: string | null): RunMetrics | null => {
    const { metrics } = useSocket(jobId);
    return metrics;
};
