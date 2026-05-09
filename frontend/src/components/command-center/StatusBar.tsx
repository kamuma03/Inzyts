import { type FC } from 'react';
import type { PhaseStatus } from '../../api';

interface StatusBarProps {
    isConnected: boolean;
    phases: PhaseStatus[] | null;
}

interface ShortcutHint {
    keys: string;
    label: string;
}

const SHORTCUT_HINTS: ShortcutHint[] = [
    { keys: 'J / K', label: 'next / prev event' },
    { keys: '1–6', label: 'switch tab' },
    { keys: '⌘↵', label: 're-run' },
    { keys: 'Esc', label: 'clear selection' },
];

/** Bottom status bar — connection dot, retries summary across phases,
 *  and keyboard shortcut hints. No kernel/sandbox state in V1. */
export const StatusBar: FC<StatusBarProps> = ({ isConnected, phases }) => {
    const totalRetries = (phases ?? []).reduce((acc, p) => acc + (p.retries || 0), 0);

    return (
        <footer
            role="status"
            aria-live="polite"
            className="shrink-0 flex items-center gap-3 px-3 py-1.5 border border-[var(--rule)] rounded-lg bg-[var(--surface-1)] text-[12px]"
        >
            {/* Connection + retries — only render when something is wrong or
                worth knowing. A persistent "live" dot is reassuring once and
                noise forever after. */}
            {(!isConnected || totalRetries > 0) && (
                <>
                    {!isConnected && (
                        <span className="flex items-center gap-1.5">
                            <span
                                className="inline-block w-1.5 h-1.5 rounded-full"
                                style={{ backgroundColor: 'var(--bad)' }}
                                aria-label="disconnected"
                            />
                            <span className="text-[var(--text-dim)] uppercase tracking-[0.04em]">
                                offline
                            </span>
                        </span>
                    )}
                    {totalRetries > 0 && (
                        <>
                            {!isConnected && <span className="text-[var(--text-dim)]">·</span>}
                            <span className="flex items-center gap-1.5">
                                <span className="font-mono text-[var(--text-secondary)]">{totalRetries}</span>
                                <span className="uppercase tracking-[0.04em] text-[var(--text-dim)]">retries</span>
                            </span>
                        </>
                    )}
                </>
            )}

            <div className="flex-1" />

            {/* Shortcut hints — hidden below lg so the bar doesn't wrap when
                the offline / retries chips appear at narrow widths. */}
            <ul className="hidden lg:flex items-center gap-3 m-0 p-0 list-none">
                {SHORTCUT_HINTS.map((h) => (
                    <li key={h.keys} className="flex items-center gap-1.5">
                        <kbd className="font-mono px-1 py-px bg-[rgba(255,255,255,0.05)] rounded text-[var(--text-secondary)]">
                            {h.keys}
                        </kbd>
                        <span className="text-[var(--text-dim)]">{h.label}</span>
                    </li>
                ))}
            </ul>
        </footer>
    );
};
