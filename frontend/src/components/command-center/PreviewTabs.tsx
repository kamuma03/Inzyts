import { type FC, type ReactNode } from 'react';

export type PreviewTabId = 'overview' | 'visual' | 'code' | 'data' | 'logs' | 'events';

export interface PreviewTabDef<T extends PreviewTabId = PreviewTabId> {
    id: T;
    label: string;
    /** Optional badge content (e.g. status pill on the Code tab while streaming). */
    badge?: ReactNode;
}

interface PreviewTabsProps<T extends PreviewTabId> {
    tabs: PreviewTabDef<T>[];
    activeTab: T;
    onChange: (id: T) => void;
    children: Partial<Record<T, ReactNode>>;
}

/** Tabbed preview surface, generic over the subset of PreviewTabIds that a
 *  given group renders. Results uses the four-id subset; Run uses the
 *  two-id subset. The generic stops callers from passing an activeTab id
 *  that isn't part of the supplied tabs[].
 *
 *  All tabs are rendered into the DOM at once and toggled with `hidden`
 *  so each panel keeps its native scroll position when toggled out and
 *  back in — cheaper than re-rendering large panels on every switch. */
export const PreviewTabs = <T extends PreviewTabId>({
    tabs,
    activeTab,
    onChange,
    children,
}: PreviewTabsProps<T>) => {
    return (
        <div className="flex flex-col h-full min-h-0">
            <div
                role="tablist"
                aria-label="Preview tabs"
                className="shrink-0 flex items-center gap-1 px-3 border-b border-[var(--rule)]"
            >
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        role="tab"
                        aria-selected={activeTab === tab.id}
                        aria-controls={`tabpanel-${tab.id}`}
                        id={`tab-${tab.id}`}
                        tabIndex={activeTab === tab.id ? 0 : -1}
                        onClick={() => onChange(tab.id)}
                        className={`px-3 py-2 text-[12px] font-medium border-b-2 transition-colors ${
                            activeTab === tab.id
                                ? 'border-[var(--accent)] text-[var(--accent)]'
                                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`}
                    >
                        <span>{tab.label}</span>
                        {tab.badge != null && <span className="ml-1.5">{tab.badge}</span>}
                    </button>
                ))}
            </div>

            <div className="flex-1 min-h-0 relative">
                {tabs.map((tab) => (
                    <PreviewPanel
                        key={tab.id}
                        id={tab.id}
                        active={activeTab === tab.id}
                    >
                        {children[tab.id]}
                    </PreviewPanel>
                ))}
            </div>
        </div>
    );
};

interface PreviewPanelProps {
    id: PreviewTabId;
    active: boolean;
    children: ReactNode;
}

/** One panel — kept mounted and toggled with `hidden` so the browser preserves
 *  its native scroll position automatically when the user returns. */
const PreviewPanel: FC<PreviewPanelProps> = ({ id, active, children }) => (
    <div
        role="tabpanel"
        id={`tabpanel-${id}`}
        aria-labelledby={`tab-${id}`}
        hidden={!active}
        className="absolute inset-0 overflow-auto"
    >
        {children}
    </div>
);
