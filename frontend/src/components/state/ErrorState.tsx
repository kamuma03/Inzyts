import { useState, type FC } from 'react';
import { AlertTriangle, Loader2, ChevronDown } from 'lucide-react';

interface ErrorStateProps {
    /** What didn't load — under 6 words. Never include a raw error
     *  message in the title; that goes behind `details`. */
    title: string;
    /** Two sentences max: (1) reassure prior work is safe,
     *  (2) tell the user what to do. */
    body?: string;
    /** Wires to the same fetch fn that failed. Required when the
     *  failure is recoverable at the panel level. */
    onRetry?: () => void;
    /** Disables the Retry button + shows a spinner alongside it. */
    retrying?: boolean;
    /** Stack / HTTP code / raw err.message — surfaced behind a
     *  "Show details" disclosure for power users, never in the title. */
    details?: string;
    className?: string;
}

/** Canonical recoverable-failure state. Replaces the AlertTriangle +
 *  red-text pattern that previously required a page refresh to retry.
 *  Retry is the next desired action, so it uses --accent (not an alarm
 *  colour). Tints flow through color-mix(in srgb, var(--bad) X%,
 *  transparent) — no raw rgba. */
export const ErrorState: FC<ErrorStateProps> = ({
    title,
    body,
    onRetry,
    retrying = false,
    details,
    className = '',
}) => {
    const [detailsOpen, setDetailsOpen] = useState(false);

    return (
        <div
            role="alert"
            className={`flex flex-col items-center justify-center gap-3 py-12 px-6 text-center ${className}`.trim()}
        >
            <div className="w-10 h-10 rounded-full bg-[color-mix(in_srgb,var(--bad)_15%,transparent)] flex items-center justify-center">
                <AlertTriangle size={20} className="text-[var(--bad)]" />
            </div>
            <div className="flex flex-col gap-1 max-w-[360px]">
                <h3 className="m-0 text-[14px] font-medium text-[var(--text-primary)]">
                    {title}
                </h3>
                {body && (
                    <p className="m-0 text-[12px] text-[var(--text-secondary)] leading-[1.5] [text-wrap:pretty]">
                        {body}
                    </p>
                )}
            </div>
            {onRetry && (
                <button
                    type="button"
                    onClick={onRetry}
                    disabled={retrying}
                    className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--accent-soft)] text-[var(--accent)] text-[12px] font-semibold border border-[color-mix(in_srgb,var(--accent)_25%,transparent)] hover:bg-[color-mix(in_srgb,var(--accent)_18%,transparent)] hover:border-[var(--accent)] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                    {retrying && <Loader2 size={14} className="animate-spin" />}
                    {retrying ? 'Retrying…' : 'Retry'}
                </button>
            )}
            {details && (
                <details
                    open={detailsOpen}
                    onToggle={(e) => setDetailsOpen((e.target as HTMLDetailsElement).open)}
                    className="mt-2 max-w-[480px] w-full text-left"
                >
                    <summary className="cursor-pointer text-[11px] text-[var(--text-dim)] hover:text-[var(--text-secondary)] flex items-center gap-1 list-none [&::-webkit-details-marker]:hidden transition-colors">
                        <ChevronDown size={12} className={`transition-transform ${detailsOpen ? 'rotate-0' : '-rotate-90'}`} />
                        Show details
                    </summary>
                    <pre className="mt-2 p-2 text-[11px] font-mono text-[var(--text-secondary)] bg-white/[0.04] border border-[var(--rule)] rounded whitespace-pre-wrap break-words max-h-[200px] overflow-auto">
                        {details}
                    </pre>
                </details>
            )}
        </div>
    );
};
