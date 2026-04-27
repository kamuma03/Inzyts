/**
 * Format a duration in seconds to a human-readable string.
 * Examples: 45 -> "45s", 90 -> "1m 30s", 120 -> "2m"
 */
export const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
};

/**
 * Extract the filename from a file path.
 * Returns "Unknown File" if the path is empty or undefined.
 */
export const getFileName = (path?: string): string => {
    if (!path) return 'Unknown File';
    return path.split('/').pop() || path;
};

/**
 * Format a date string to a locale-specific representation.
 */
export const formatDate = (dateStr: string): string => {
    return new Date(dateStr).toLocaleString();
};

/**
 * Format a USD amount with appropriate precision.
 * < $1 → 4 decimals, < $100 → 2 decimals, otherwise integer.
 */
export const formatCost = (usd: number | null | undefined): string => {
    if (usd == null || !Number.isFinite(usd)) return '—';
    if (usd === 0) return '$0';
    if (Math.abs(usd) < 0.01) return `$${usd.toFixed(4)}`;
    if (Math.abs(usd) < 100) return `$${usd.toFixed(2)}`;
    return `$${Math.round(usd).toLocaleString()}`;
};

/**
 * Format a token count for compact display: 1234 → "1.2K", 1_500_000 → "1.5M".
 */
export const formatTokens = (n: number | null | undefined): string => {
    if (n == null || !Number.isFinite(n)) return '—';
    if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return `${Math.round(n)}`;
};

/**
 * Format a byte count: 1024 → "1.0 KB", 5_242_880 → "5.0 MB".
 */
export const formatBytes = (bytes: number | null | undefined): string => {
    if (bytes == null || !Number.isFinite(bytes)) return '—';
    const abs = Math.abs(bytes);
    if (abs < 1024) return `${bytes} B`;
    if (abs < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (abs < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};

export interface DeltaResult {
    label: string;          // e.g. "-12s" or "+$0.07" or "—" when no comparison
    direction: 'better' | 'worse' | 'same' | 'none';
}

/**
 * Compute a delta vs. a previous value with direction relative to whether
 * lower is better (e.g. cost, elapsed) or higher is better (quality_score).
 *
 * Returns a structured result so the UI can render colour and label.
 */
export const formatDelta = (
    current: number | null | undefined,
    previous: number | null | undefined,
    {
        lowerIsBetter = true,
        unit = '',
        formatter,
    }: {
        lowerIsBetter?: boolean;
        unit?: string;
        formatter?: (n: number) => string;
    } = {},
): DeltaResult => {
    if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) {
        return { label: '—', direction: 'none' };
    }
    const diff = current - previous;
    if (diff === 0) return { label: `±0${unit}`, direction: 'same' };

    const sign = diff > 0 ? '+' : '−';
    const formatted = formatter ? formatter(Math.abs(diff)) : `${Math.abs(diff)}${unit}`;
    const direction: DeltaResult['direction'] = lowerIsBetter
        ? (diff < 0 ? 'better' : 'worse')
        : (diff > 0 ? 'better' : 'worse');
    return { label: `${sign}${formatted}`, direction };
};
