import { useEffect, useState } from 'react';
import { CommandCenterAPI, type ColumnProfile } from '../api';

interface State {
    columns: ColumnProfile[] | null;
    loading: boolean;
    error: string | null;
}

const cache = new Map<string, ColumnProfile[]>();

/** SWR-style fetch of /jobs/{id}/columns with a small in-memory cache. */
export const useColumnProfile = (jobId: string | null) => {
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
        if (cached) {
            setState({ columns: cached, loading: false, error: null });
            return;
        }

        let cancelled = false;
        setState((prev) => ({ ...prev, loading: true, error: null }));

        CommandCenterAPI.getColumns(jobId)
            .then((cols) => {
                if (cancelled) return;
                cache.set(jobId, cols);
                setState({ columns: cols, loading: false, error: null });
            })
            .catch((err) => {
                if (cancelled) return;
                setState({
                    columns: null,
                    loading: false,
                    error: err?.message ?? 'Failed to load column profile',
                });
            });

        return () => {
            cancelled = true;
        };
    }, [jobId]);

    return state;
};
