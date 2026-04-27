import { useCallback, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JobSummary } from '../../api';
import { useJobContext } from '../../context/JobContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useMetricsHistory } from '../../hooks/useRunMetrics';
import { TopStrip } from './TopStrip';
import { PreviewTabs, type PreviewTabId } from './PreviewTabs';
import { OverviewPanel } from './panels/OverviewPanel';
import { VisualPanel } from './panels/VisualPanel';
import { CodePanel } from './panels/CodePanel';
import { DataPanel } from './panels/DataPanel';
import { LogsPanel } from './panels/LogsPanel';
import { TrafficRow } from './TrafficRow';
import { EventStream } from './EventStream';
import { StatusBar } from './StatusBar';

interface CommandCenterViewProps {
    job: JobSummary;
}

const TAB_DEFS = [
    { id: 'overview' as const, label: 'Overview' },
    { id: 'visual' as const, label: 'Visual' },
    { id: 'code' as const, label: 'Code' },
    { id: 'data' as const, label: 'Data' },
    { id: 'logs' as const, label: 'Logs' },
    { id: 'events' as const, label: 'Events' },
];

const TAB_BY_HOTKEY: Record<string, PreviewTabId> = {
    '1': 'overview',
    '2': 'visual',
    '3': 'code',
    '4': 'data',
    '5': 'logs',
    '6': 'events',
};

const DEFAULT_TAB_FOR_STATUS = (status: string): PreviewTabId =>
    status === 'completed' ? 'visual' : 'overview';

/** Top-level analyst surface. All contextual information (pipeline, columns,
 *  cost, question) and all output views (notebook, code, data, logs, events)
 *  are top-level tabs sharing the full page width. The previous 3-column
 *  layout with cramped side rails is gone. */
export const CommandCenterView: FC<CommandCenterViewProps> = ({ job }) => {
    const navigate = useNavigate();
    const { logs, events, metrics, phases, isConnected, handleCancelJob } = useJobContext();
    const history = useMetricsHistory(metrics, job.id);

    const [selectedColumn, setSelectedColumn] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<PreviewTabId>(() =>
        DEFAULT_TAB_FOR_STATUS(job.status),
    );

    const isCompleted = job.status === 'completed';
    const isRunning = job.status === 'running' || job.status === 'pending';

    const handleRerun = useCallback(() => {
        // ⌘↵ goes back to the home form so users can tweak params before re-running.
        navigate('/');
    }, [navigate]);

    useKeyboardShortcuts(
        {
            escape: () => setSelectedColumn(null),
            '1': () => setActiveTab(TAB_BY_HOTKEY['1']),
            '2': () => setActiveTab(TAB_BY_HOTKEY['2']),
            '3': () => setActiveTab(TAB_BY_HOTKEY['3']),
            '4': () => setActiveTab(TAB_BY_HOTKEY['4']),
            '5': () => setActiveTab(TAB_BY_HOTKEY['5']),
            '6': () => setActiveTab(TAB_BY_HOTKEY['6']),
            'cmd+enter': handleRerun,
            'ctrl+enter': handleRerun,
        },
        { enabled: true },
    );

    const codeStreaming = !isCompleted;
    const tabs = TAB_DEFS.map((t) => {
        if (t.id === 'code') {
            return {
                ...t,
                badge: (
                    <span
                        className={`inline-flex items-center gap-1 px-1 py-px text-[9px] uppercase tracking-[1px] rounded ${
                            codeStreaming
                                ? 'bg-[rgba(76,201,240,0.12)] text-[var(--bg-turquoise-surf)]'
                                : 'bg-[rgba(52,211,153,0.12)] text-[var(--status-good)]'
                        }`}
                    >
                        <span
                            className={`inline-block w-1.5 h-1.5 rounded-full ${codeStreaming ? 'animate-pulse' : ''}`}
                            style={{
                                backgroundColor: codeStreaming
                                    ? 'var(--bg-turquoise-surf)'
                                    : 'var(--status-good)',
                            }}
                        />
                        {codeStreaming ? 'streaming' : 'ready'}
                    </span>
                ),
            };
        }
        if (t.id === 'events' && events.length > 0) {
            return {
                ...t,
                badge: (
                    <span className="inline-flex items-center px-1 py-px text-[9px] font-mono rounded bg-[rgba(255,255,255,0.06)] text-[var(--text-secondary)]">
                        {events.length}
                    </span>
                ),
            };
        }
        return t;
    });

    return (
        <div className="flex-1 flex flex-col gap-3 min-h-0 min-w-0">
            <TopStrip
                job={job}
                metrics={metrics}
                onCancel={handleCancelJob}
                onExport={isCompleted ? () => navigate(`/jobs/${job.id}`) : undefined}
            />

            {isRunning && <TrafficRow history={history} />}

            <div className="flex-1 min-h-0 min-w-0 border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)] overflow-hidden flex flex-col">
                <PreviewTabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab}>
                    {{
                        overview: (
                            <OverviewPanel
                                job={job}
                                phases={phases}
                                selectedColumn={selectedColumn}
                                onSelectColumn={setSelectedColumn}
                            />
                        ),
                        visual: <VisualPanel job={job} />,
                        code: <CodePanel job={job} events={events} />,
                        data: <DataPanel jobId={job.id} />,
                        logs: <LogsPanel logs={logs} />,
                        events: (
                            <div className="h-full p-2">
                                <EventStream events={events} />
                            </div>
                        ),
                    }}
                </PreviewTabs>
            </div>

            <StatusBar isConnected={isConnected} phases={phases} />
        </div>
    );
};
