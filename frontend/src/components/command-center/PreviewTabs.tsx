import { type FC, type ReactNode } from 'react';

export type PreviewTabId = 'overview' | 'visual' | 'code' | 'data' | 'logs' | 'events';

export interface PreviewTabDef<T extends PreviewTabId = PreviewTabId> {
    id: T;
    label: string;
    /** Optional badge content (e.g. status pill on the Code tab while streaming). */
    badge?: ReactNode;
}

interface PreviewTabBarProps<T extends PreviewTabId> {
    tabs: PreviewTabDef<T>[];
    activeTab: T;
    onChange: (id: T) => void;
    /** Optional content rendered to the left of the tab buttons — e.g. the
     *  Results/Run segmented control that shares the row in option B. */
    prefix?: ReactNode;
    ariaLabel?: string;
}

/** The tab strip portion of the preview surface — renders as a row of tab
 *  buttons. Decoupled from PreviewTabPanels so callers can inline a
 *  segmented control or other chrome alongside the tabs on the same row. */
export const PreviewTabBar = <T extends PreviewTabId>({
    tabs,
    activeTab,
    onChange,
    prefix,
    ariaLabel = 'Preview tabs',
}: PreviewTabBarProps<T>) => (
    <div
        role="tablist"
        aria-label={ariaLabel}
        className="shrink-0 flex items-center gap-1 px-3 border-b border-[var(--rule)]"
    >
        {prefix}
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
);

interface PreviewTabPanelsProps<T extends PreviewTabId> {
    tabs: PreviewTabDef<T>[];
    activeTab: T;
    children: Partial<Record<T, ReactNode>>;
}

/** The panels portion. All tabs render at once and toggle with `hidden`,
 *  so the browser preserves each panel's scroll position natively. */
export const PreviewTabPanels = <T extends PreviewTabId>({
    tabs,
    activeTab,
    children,
}: PreviewTabPanelsProps<T>) => (
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
);

interface PreviewTabsProps<T extends PreviewTabId> {
    tabs: PreviewTabDef<T>[];
    activeTab: T;
    onChange: (id: T) => void;
    children: Partial<Record<T, ReactNode>>;
}

/** Convenience wrapper for the simple case where the strip and panels live
 *  in the same vertical stack. CommandCenterView composes the bar and panels
 *  separately so it can inline the Results/Run pill into the strip. */
export const PreviewTabs = <T extends PreviewTabId>({
    tabs,
    activeTab,
    onChange,
    children,
}: PreviewTabsProps<T>) => (
    <div className="flex flex-col h-full min-h-0">
        <PreviewTabBar tabs={tabs} activeTab={activeTab} onChange={onChange} />
        <PreviewTabPanels tabs={tabs} activeTab={activeTab}>
            {children}
        </PreviewTabPanels>
    </div>
);

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
