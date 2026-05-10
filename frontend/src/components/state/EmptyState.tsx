import { type FC } from 'react';
import { Inbox, Database, Terminal, Activity, Search, FileText, type LucideIcon } from 'lucide-react';

export type EmptyStateIcon = 'inbox' | 'database' | 'terminal' | 'activity' | 'search' | 'file';

const ICON_MAP: Record<EmptyStateIcon, LucideIcon> = {
    inbox: Inbox,
    database: Database,
    terminal: Terminal,
    activity: Activity,
    search: Search,
    file: FileText,
};

interface EmptyStateProps {
    icon: EmptyStateIcon;
    /** Factual + scoped: "No analyses yet", not "You haven't created…". */
    title: string;
    /** One sentence telling the user how to populate. Skip if obvious. */
    body?: string;
    /** Only when there's a meaningful next action and it isn't already
     *  on screen. Uses --accent-soft, never an alarm colour. */
    cta?: { label: string; onClick: () => void };
    /** Inline variant — drops the icon, smaller copy. Use when EmptyState
     *  sits alongside other content rather than filling a panel. */
    compact?: boolean;
    className?: string;
}

/** Canonical "request succeeded, zero results" state. Replaces the
 *  ad-hoc empty messages scattered across panels. Empty isn't an
 *  error — no alarm copy ("Sorry…"), no destructive colours, no
 *  apology. Same chrome every time. */
export const EmptyState: FC<EmptyStateProps> = ({
    icon,
    title,
    body,
    cta,
    compact = false,
    className = '',
}) => {
    const Icon = ICON_MAP[icon];

    if (compact) {
        return (
            <div className={`flex items-center gap-2 py-2 text-[12px] text-[var(--text-dim)] ${className}`.trim()}>
                <Icon size={14} />
                <span>{title}</span>
                {body && <span className="opacity-70">— {body}</span>}
            </div>
        );
    }

    return (
        <div
            className={`flex flex-col items-center justify-center gap-3 py-12 px-6 text-center ${className}`.trim()}
        >
            <div className="w-10 h-10 rounded-full bg-[var(--surface-2)] flex items-center justify-center">
                <Icon size={20} className="text-[var(--text-dim)]" />
            </div>
            <div className="flex flex-col gap-1 max-w-[320px]">
                <h3 className="m-0 text-[14px] font-medium text-[var(--text-primary)]">
                    {title}
                </h3>
                {body && (
                    <p className="m-0 text-[12px] text-[var(--text-secondary)] leading-[1.5] [text-wrap:pretty]">
                        {body}
                    </p>
                )}
            </div>
            {cta && (
                <button
                    type="button"
                    onClick={cta.onClick}
                    className="mt-1 px-3 py-1.5 rounded-md bg-[var(--accent-soft)] text-[var(--accent)] text-[12px] font-semibold border border-[color-mix(in_srgb,var(--accent)_25%,transparent)] hover:bg-[color-mix(in_srgb,var(--accent)_18%,transparent)] hover:border-[var(--accent)] transition-colors"
                >
                    {cta.label}
                </button>
            )}
        </div>
    );
};
