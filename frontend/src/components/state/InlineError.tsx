import { type FC, type ReactNode } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface InlineErrorProps {
    children: ReactNode;
    /** Optional dismiss button. Most inline errors auto-clear when the
     *  offending input changes — only pass `onDismiss` when there's no
     *  natural causal-input the user can fix. */
    onDismiss?: () => void;
    className?: string;
}

/** Field-level / surface-level error sitting next to working UI. Lead
 *  with what's wrong, then the fix — single sentence. Position directly
 *  below the field that caused it, or above the submit button for
 *  whole-form failures. */
export const InlineError: FC<InlineErrorProps> = ({ children, onDismiss, className = '' }) => (
    <div
        role="alert"
        className={`flex items-start gap-2 px-3 py-2 rounded-md border bg-[color-mix(in_srgb,var(--bad)_8%,transparent)] border-[color-mix(in_srgb,var(--bad)_30%,transparent)] text-[var(--bad)] text-[13px] leading-[1.4] ${className}`.trim()}
    >
        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
        <div className="flex-1 [text-wrap:pretty]">{children}</div>
        {onDismiss && (
            <button
                type="button"
                onClick={onDismiss}
                aria-label="Dismiss"
                className="shrink-0 bg-transparent border-none cursor-pointer text-[var(--bad)] opacity-70 hover:opacity-100 transition-opacity p-0"
            >
                <X size={14} />
            </button>
        )}
    </div>
);
