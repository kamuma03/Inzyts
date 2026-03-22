import React, { useEffect, useRef } from 'react';
import { LogMessage } from '../hooks/useSocket';
// @ts-expect-error - Vite resolves this to CJS, but TS expects the broken ESM types
import { FixedSizeList } from 'react-window';
const List = FixedSizeList;
import { AutoSizer } from 'react-virtualized-auto-sizer';

interface LogViewerProps {
    logs: LogMessage[];
    height?: string;
}

export const LogViewer: React.FC<LogViewerProps> = ({ logs }) => {
    const listRef = useRef<FixedSizeList>(null);

    useEffect(() => {
        if (logs.length > 0 && listRef.current) {
            listRef.current.scrollToItem(logs.length - 1, 'end');
        }
    }, [logs.length]);

    const Row = ({ index, style }: { index: number, style: React.CSSProperties }) => {
        const log = logs[index];
        return (
            <div style={style} className="mb-1 whitespace-nowrap overflow-hidden text-ellipsis">
                <span className="text-[var(--bg-blue-green)] mr-2">
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
        );
    };

    return (
        <div className="bg-[var(--bg-deep-twilight)] text-[var(--text-secondary)] font-mono p-4 rounded-lg flex-1 min-h-0 border border-[var(--border-color)] h-full">
            {/* @ts-expect-error - AutoSizer types from DefinitelyTyped are occasionally mismatched */}
            <AutoSizer>
                {({ height, width }: { height: number; width: number }) => (
                    <List
                        ref={listRef}
                        height={height}
                        itemCount={logs.length}
                        itemSize={24}
                        width={width}
                    >
                        {Row}
                    </List>
                )}
            </AutoSizer>
        </div>
    );
};
