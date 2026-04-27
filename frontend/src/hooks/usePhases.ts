import { useSocket } from './useSocket';
import type { PhaseStatus } from '../api';

/** Subscribes to ``phase_update`` and returns the latest pipeline snapshot. */
export const usePhases = (jobId: string | null): PhaseStatus[] | null => {
    const { phases } = useSocket(jobId);
    return phases;
};
