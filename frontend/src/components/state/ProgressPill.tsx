import { type FC } from 'react';
import { Loader2 } from 'lucide-react';

type Intent = 'accent' | 'ok' | 'warn' | 'bad';
type Indicator = 'dot' | 'spinner' | 'none';

interface ProgressPillProps {
    intent: Intent;
    /** "Connected", "Reconnecting", "Generating PDF". */
    caption: string;
    /** Defaults to 'spinner' for accent (in-flight ops), 'dot' for
     *  ok / warn / bad (steady-state status). */
    indicator?: Indicator;
    /** Optional — opens a detail popover or cancels the op. */
    onClick?: () => void;
    className?: string;
}

const TINT_CLASS: Record<Intent, string> = {
    accent: 'bg-[var(--accent-soft)] text-[var(--accent)] border-[color-mix(in_srgb,var(--accent)_25%,transparent)]',
    ok: 'bg-[color-mix(in_srgb,var(--ok)_15%,transparent)] text-[var(--ok)] border-[color-mix(in_srgb,var(--ok)_35%,transparent)]',
    warn: 'bg-[color-mix(in_srgb,var(--warn)_15%,transparent)] text-[var(--warn)] border-[color-mix(in_srgb,var(--warn)_35%,transparent)]',
    bad: 'bg-[color-mix(in_srgb,var(--bad)_12%,transparent)] text-[var(--bad)] border-[color-mix(in_srgb,var(--bad)_30%,transparent)]',
};

const DOT_COLOR: Record<Intent, string> = {
    accent: 'var(--accent)',
    ok: 'var(--ok)',
    warn: 'var(--warn)',
    bad: 'var(--bad)',
};

/** Ambient background-op status — header bar / top strip / status bar.
 *  If the user must act on it, promote to a Toast or InlineError. */
export const ProgressPill: FC<ProgressPillProps> = ({
    intent,
    caption,
    indicator,
    onClick,
    className = '',
}) => {
    const resolvedIndicator: Indicator = indicator ?? (intent === 'accent' ? 'spinner' : 'dot');
    const baseClass = `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-semibold border transition-colors ${TINT_CLASS[intent]}`;

    const content = (
        <>
            {resolvedIndicator === 'spinner' && (
                <Loader2 size={11} className="animate-spin" />
            )}
            {resolvedIndicator === 'dot' && (
                <span
                    className={`inline-block w-1.5 h-1.5 rounded-full ${intent === 'warn' ? 'animate-pulse' : ''}`}
                    style={{ backgroundColor: DOT_COLOR[intent] }}
                    aria-hidden="true"
                />
            )}
            <span>{caption}</span>
        </>
    );

    if (onClick) {
        return (
            <button
                type="button"
                onClick={onClick}
                className={`${baseClass} cursor-pointer hover:brightness-110 ${className}`.trim()}
            >
                {content}
            </button>
        );
    }

    return (
        <span
            role="status"
            aria-live="polite"
            className={`${baseClass} ${className}`.trim()}
        >
            {content}
        </span>
    );
};
