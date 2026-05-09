import React, { useEffect, useRef } from 'react';
import { LogMessage } from '../hooks/useSocket';

interface LogViewerProps {
    logs: LogMessage[];
}

export const LogViewer: React.FC<LogViewerProps> = ({ logs }) => {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs.length]);

    if (logs.length === 0) {
        return (
            <div className="bg-[var(--surface-0)] text-[var(--text-secondary)] font-mono p-4 rounded-lg flex-1 min-h-0 border border-[var(--rule)] flex items-center justify-center">
                No logs available.
            </div>
        );
    }

    return (
        <div className="bg-[var(--surface-0)] text-[var(--text-secondary)] font-mono text-[0.82rem] leading-[1.7] rounded-lg flex-1 min-h-0 border border-[var(--rule)] overflow-y-auto p-4">
            {logs.map((log, index) => (
                <div key={`${log.timestamp}-${index}`} className="whitespace-nowrap overflow-hidden text-ellipsis">
                    <span className="text-[var(--accent)] mr-2">
                        [{new Date(log.timestamp).toLocaleTimeString()}]
                    </span>
                    <span
                        className={
                            log.level === 'ERROR' ? 'text-red-400' :
                            log.level === 'WARNING' ? 'text-yellow-400' : 'text-[var(--text-primary)]'
                        }
                        title={log.message}
                    >
                        {log.message}
                    </span>
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
};
