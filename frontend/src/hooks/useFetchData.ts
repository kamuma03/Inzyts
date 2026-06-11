import { useState, useEffect, useCallback, useRef } from 'react';
import { getErrorMessage } from '../utils/errorMessage';

interface UseFetchDataResult<T> {
    data: T | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useFetchData<T>(
    fetchFn: () => Promise<T>,
    deps: any[],
    options?: { enabled?: boolean }
): UseFetchDataResult<T> {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const mountedRef = useRef(true);
    const fetchRef = useRef(fetchFn);
    fetchRef.current = fetchFn;

    const enabled = options?.enabled ?? true;

    const doFetch = useCallback(async () => {
        if (!enabled) return;

        setLoading(true);
        setError(null);

        try {
            const result = await fetchRef.current();
            if (mountedRef.current) {
                setData(result);
            }
        } catch (err: unknown) {
            if (mountedRef.current) {
                setError(getErrorMessage(err));
            }
        } finally {
            if (mountedRef.current) {
                setLoading(false);
            }
        }
    }, [enabled, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        mountedRef.current = true;
        doFetch();
        return () => {
            mountedRef.current = false;
        };
    }, [doFetch]);

    return { data, loading, error, refetch: doFetch };
}
