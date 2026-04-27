import { type FC } from 'react';
import { LogViewer } from '../../LogViewer';
import type { LogMessage } from '../../../hooks/useSocket';

interface LogsPanelProps {
    logs: LogMessage[];
}

/** Logs tab — wraps the existing LogViewer. */
export const LogsPanel: FC<LogsPanelProps> = ({ logs }) => (
    <div className="h-full">
        <LogViewer logs={logs} />
    </div>
);
