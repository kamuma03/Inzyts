/**
 * Extract a human-readable message from an unknown thrown value.
 *
 * Prefers a FastAPI error body (`response.data.detail`), then a standard
 * Error/axios `message`, then a raw string, falling back to a supplied
 * default. Centralised so every component surfaces backend errors the same
 * way instead of each reaching into a different field.
 */
export function getErrorMessage(err: unknown, fallback = 'An error occurred'): string {
    if (typeof err === 'string') return err;
    if (err && typeof err === 'object') {
        const e = err as {
            response?: { data?: { detail?: unknown } };
            message?: unknown;
        };
        const detail = e.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
        if (typeof e.message === 'string' && e.message.trim()) return e.message;
    }
    return fallback;
}
