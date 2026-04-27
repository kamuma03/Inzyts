import { useCallback, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JobSummary } from '../../api';
import { useJobContext } from '../../context/JobContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useMetricsHistory } from '../../hooks/useRunMetrics';
import { TopStrip } from './TopStrip';
import { PipelineRail } from './PipelineRail';
import { ColumnInspector } from './ColumnInspector';
import { CostBreakdown } from './CostBreakdown';
import { QuestionCard } from './QuestionCard';
import { PreviewTabs, type PreviewTabId } from './PreviewTabs';
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
    { id: 'visual' as const, label: 'Visual' },
    { id: 'code' as const, label: 'Code' },
    { id: 'data' as const, label: 'Data' },
    { id: 'logs' as const, label: 'Logs' },
    { id: 'events' as const, label: 'Events' },
];

const TAB_BY_HOTKEY: Record<string, PreviewTabId> = {
    '1': 'visual',
    '2': 'code',
    '3': 'data',
    '4': 'logs',
    '5': 'events',
};

/** Top-level orchestrator for the analyst surface. */
export const CommandCenterView: FC<CommandCenterViewProps> = ({ job }) => {
    const navigate = useNavigate();
    const { logs, events, metrics, phases, isConnected, handleCancelJob } = useJobContext();
    const history = useMetricsHistory(metrics, job.id);

    const [selectedColumn, setSelectedColumn] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<PreviewTabId>('visual');

    const isCompleted = job.status === 'completed';

    const handleRerun = useCallback(() => {
        // Re-runs go via the home form so the user can tweak params.
        // ⌘↵ navigates back; the form pre-fills from initialFormState if wired upstream.
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
            'cmd+enter': handleRerun,
            'ctrl+enter': handleRerun,
        },
        { enabled: true },
    );

    const isRunning = job.status === 'running' || job.status === 'pending';

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

            <div
                className="flex-1 grid gap-3 min-h-0"
                style={{ gridTemplateColumns: '270px 1fr 320px' }}
            >
                {/* Left rail */}
                <PipelineRail phases={phases} mode={job.mode} />

                {/* Center stack — PreviewTabs takes full vertical space.
                    TrafficRow is shown only while the job is actively running
                    (live signals are stale post-completion); EventStream now
                    lives inside the tabs as its 5th panel. */}
                <main className="flex flex-col gap-3 min-h-0 min-w-0">
                    {isRunning && <TrafficRow history={history} />}

                    <div className="flex-1 min-h-0 border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)] overflow-hidden flex flex-col">
                        <PreviewTabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab}>
                            {{
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
                </main>

                {/* Right rail */}
                <aside className="flex flex-col gap-3 min-h-0 min-w-0">
                    <QuestionCard question={job.question ?? null} />
                    <div className="flex-1 min-h-0 min-w-0">
                        <ColumnInspector
                            jobId={job.id}
                            selectedColumn={selectedColumn}
                            onSelect={setSelectedColumn}
                        />
                    </div>
                    <CostBreakdown jobId={job.id} refreshKey={job.status} />
                </aside>
            </div>

            <StatusBar isConnected={isConnected} phases={phases} />
        </div>
    );
};
