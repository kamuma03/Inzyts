import type { FC, ReactNode } from 'react';

export interface TabItem {
    id: string;
    label: string;
    icon?: ReactNode;
}

interface TabsProps {
    tabs: TabItem[];
    activeTab: string;
    onSelect: (id: string) => void;
    ariaLabel?: string;
}

export const Tabs: FC<TabsProps> = ({ tabs, activeTab, onSelect, ariaLabel = 'Tabs' }) => {
    return (
        <div
            role="tablist"
            aria-label={ariaLabel}
            className="flex gap-1 border-b border-[var(--border-color)] flex-wrap"
        >
            {tabs.map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                    <button
                        key={tab.id}
                        type="button"
                        role="tab"
                        aria-selected={isActive}
                        aria-controls={`tabpanel-${tab.id}`}
                        id={`tab-${tab.id}`}
                        onClick={() => onSelect(tab.id)}
                        className={`flex items-center gap-[0.4rem] px-4 py-[0.6rem] text-[0.9rem] bg-none border-none border-b-2 cursor-pointer transition-[color,border-color] duration-200 whitespace-nowrap ${
                            isActive
                                ? 'text-[var(--bg-turquoise-surf)] font-semibold border-b-[var(--bg-turquoise-surf)]'
                                : 'text-[var(--text-secondary)] font-medium border-b-transparent'
                        }`}
                    >
                        {tab.icon}
                        {tab.label}
                    </button>
                );
            })}
        </div>
    );
};
