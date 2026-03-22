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
