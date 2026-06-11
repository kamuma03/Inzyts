import React, { useEffect, useRef } from 'react';
import { LogMessage } from '../hooks/useSocket';
import { EmptyState } from './state';

interface LogViewerProps {
    logs: LogMessage[];
}

export const LogViewer: React.FC<LogViewerProps> = ({ logs }) => {
    const scrollRef = useRef<HTMLDivElement>(null);
    // Only auto-follow when the user is already pinned near the bottom — if
    // they've scrolled up to read history, leave their position alone.
    const nearBottomRef = useRef(true);

    const handleScroll = () => {
        const el = scrollRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        nearBottomRef.current = distanceFromBottom < 40;
    };

    useEffect(() => {
        const el = scrollRef.current;
        if (!el || !nearBottomRef.current) return;
        // Assign scrollTop directly rather than scrollIntoView: the latter can
        // scroll an ancestor (e.g. a hidden tab panel) into view, yanking the
        // page around when this log view isn't the visible tab.
        el.scrollTop = el.scrollHeight;
    }, [logs.length]);

    if (logs.length === 0) {
        return (
            <div className="bg-[var(--surface-0)] rounded-lg flex-1 min-h-0 border border-[var(--rule)] flex items-center justify-center">
                <EmptyState
                    icon="terminal"
                    title="No logs yet"
                    body="Pipeline output will appear here as the run progresses."
                />
            </div>
        );
    }

    return (
        <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="bg-[var(--surface-0)] text-[var(--text-secondary)] font-mono text-[0.82rem] leading-[1.7] rounded-lg flex-1 min-h-0 border border-[var(--rule)] overflow-y-auto p-4"
        >
            {logs.map((log, index) => (
                <div key={`${log.timestamp}-${index}`} className="whitespace-nowrap overflow-hidden text-ellipsis">
                    <span className="text-[var(--accent)] mr-2">
                        [{new Date(log.timestamp).toLocaleTimeString()}]
                    </span>
                    <span
                        className={
                            log.level === 'ERROR' ? 'text-[var(--bad)]' :
                            log.level === 'WARNING' ? 'text-[var(--warn)]' : 'text-[var(--text-primary)]'
                        }
                        title={log.message}
                    >
                        {log.message}
                    </span>
                </div>
            ))}
        </div>
    );
};
