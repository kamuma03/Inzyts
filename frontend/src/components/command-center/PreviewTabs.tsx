import { useCallback, useRef, useState, type FC, type ReactNode } from 'react';

export type PreviewTabId = 'visual' | 'code' | 'data' | 'logs';

export interface PreviewTabDef {
    id: PreviewTabId;
    label: string;
    /** Optional badge content (e.g. status pill on the Code tab while streaming). */
    badge?: ReactNode;
}

interface PreviewTabsProps {
    tabs: PreviewTabDef[];
    activeTab: PreviewTabId;
    onChange: (id: PreviewTabId) => void;
    children: Record<PreviewTabId, ReactNode>;
}

/** Tabbed preview surface with per-tab scroll preservation.
 *
 *  All four tabs are rendered into the DOM at once and toggled with a
 *  ``hidden`` attribute. That way each tab keeps its native scroll position
 *  when the user switches away and back — required by the spec (R10) and
 *  cheaper than re-rendering large panels on every tab switch.
 */
export const PreviewTabs: FC<PreviewTabsProps> = ({ tabs, activeTab, onChange, children }) => {
    return (
        <div className="flex flex-col h-full min-h-0">
            <div
                role="tablist"
                aria-label="Preview tabs"
                className="shrink-0 flex items-center gap-1 px-3 border-b border-[var(--border-color)]"
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
                                ? 'border-[var(--bg-turquoise-surf)] text-[var(--bg-turquoise-surf)]'
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

/** One panel — keeps its scroll position when toggled out of view. */
const PreviewPanel: FC<PreviewPanelProps> = ({ id, active, children }) => {
    const ref = useRef<HTMLDivElement | null>(null);
    const [scrollTop, setScrollTop] = useState(0);

    // Capture scroll position when the panel deactivates so we can restore
    // it when the user returns. We also restore on activation in case the
    // browser cleared it (some layout reflows do).
    const onActivate = useCallback(() => {
        if (ref.current) ref.current.scrollTop = scrollTop;
    }, [scrollTop]);

    return (
        <div
            ref={ref}
            role="tabpanel"
            id={`tabpanel-${id}`}
            aria-labelledby={`tab-${id}`}
            hidden={!active}
            onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
            onTransitionEnd={onActivate}
            className="absolute inset-0 overflow-auto"
        >
            {children}
        </div>
    );
};
