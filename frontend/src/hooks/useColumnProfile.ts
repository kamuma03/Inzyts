import { useEffect, useState } from 'react';
import { CommandCenterAPI, type ColumnProfile } from '../api';

interface State {
    columns: ColumnProfile[] | null;
    loading: boolean;
    error: string | null;
}

const cache = new Map<string, ColumnProfile[]>();
const POLL_MS = 5000;

/** SWR-style fetch of /jobs/{id}/columns.
 *
 *  - Caches non-empty results per job id so revisiting a completed job is
 *    instant.
 *  - When ``jobStatus`` indicates the run is still in flight, polls every
 *    5s until the backend returns a populated profile. The previous
 *    implementation cached the empty pre-profiling response and never
 *    refetched, leaving the inspector blank for the rest of the run.
 */
export const useColumnProfile = (jobId: string | null, jobStatus?: string) => {
    const [state, setState] = useState<State>(() => ({
        columns: jobId ? cache.get(jobId) ?? null : null,
        loading: false,
        error: null,
    }));

    useEffect(() => {
        if (!jobId) {
            setState({ columns: null, loading: false, error: null });
            return;
        }

        const cached = cache.get(jobId);
        const inFlight = jobStatus === 'running' || jobStatus === 'pending';

        // Render the cached value immediately, but still re-fetch in the
        // background if the job is mid-run — columns may have materialised
        // since we last asked.
        if (cached) {
            setState({ columns: cached, loading: false, error: null });
            if (!inFlight) return;
        } else {
            setState((prev) => ({ ...prev, loading: true, error: null }));
        }

        let cancelled = false;

        const fetchOnce = async () => {
            try {
                const cols = await CommandCenterAPI.getColumns(jobId);
                if (cancelled) return cols;
                // Only cache non-empty responses; empty means "profiling
                // hasn't produced columns yet", which we don't want to
                // freeze in the module-level cache.
                if (cols && cols.length > 0) {
                    cache.set(jobId, cols);
                    setState({ columns: cols, loading: false, error: null });
                } else {
                    setState((prev) => ({
                        columns: prev.columns,
                        loading: false,
                        error: null,
                    }));
                }
                return cols;
            } catch (err: any) {
                if (cancelled) return null;
                setState((prev) => ({
                    columns: prev.columns,
                    loading: false,
                    error: err?.message ?? 'Failed to load column profile',
                }));
                return null;
            }
        };

        fetchOnce();

        if (!inFlight) {
            return () => {
                cancelled = true;
            };
        }

        const id = setInterval(async () => {
            const cols = await fetchOnce();
            // Stop polling once we have a populated profile.
            if (cols && cols.length > 0) {
                clearInterval(id);
            }
        }, POLL_MS);

        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, [jobId, jobStatus]);

    return state;
};
