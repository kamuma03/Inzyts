import { useCallback, useState, type FC, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JobSummary } from '../../api';
import { useJobContext } from '../../context/JobContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useMetricsHistory } from '../../hooks/useRunMetrics';
import { TopStrip } from './TopStrip';
import { PreviewTabs, type PreviewTabId, type PreviewTabDef } from './PreviewTabs';
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

type TopTab = 'results' | 'run';
type ResultsSubTab = Extract<PreviewTabId, 'overview' | 'visual' | 'code' | 'data'>;
type RunSubTab = Extract<PreviewTabId, 'logs' | 'events'>;

const RESULTS_TABS: { id: ResultsSubTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'visual', label: 'Visual' },
    { id: 'code', label: 'Code' },
    { id: 'data', label: 'Data' },
];

const RUN_TABS: { id: RunSubTab; label: string }[] = [
    { id: 'logs', label: 'Logs' },
    { id: 'events', label: 'Events' },
];

const DEFAULT_RESULTS_TAB_FOR_STATUS = (status: string): ResultsSubTab =>
    status === 'completed' ? 'visual' : 'overview';

/** Top-level analyst surface. Two top-level tabs ("Results" and "Run") split
 *  the six-tab original into "what came out" vs "how it ran". Each top-level
 *  tab remembers its own active sub-tab so cycling between them feels
 *  stateful. */
export const CommandCenterView: FC<CommandCenterViewProps> = ({ job }) => {
    const navigate = useNavigate();
    const { logs, events, metrics, phases, isConnected, handleCancelJob } = useJobContext();
    const history = useMetricsHistory(metrics, job.id);

    const [selectedColumn, setSelectedColumn] = useState<string | null>(null);
    const [topTab, setTopTab] = useState<TopTab>('results');
    const [resultsSubTab, setResultsSubTab] = useState<ResultsSubTab>(() =>
        DEFAULT_RESULTS_TAB_FOR_STATUS(job.status),
    );
    const [runSubTab, setRunSubTab] = useState<RunSubTab>('logs');

    const isCompleted = job.status === 'completed';
    const isRunning = job.status === 'running' || job.status === 'pending';

    const handleRerun = useCallback(() => {
        // ⌘↵ goes back to the home form so users can tweak params before re-running.
        navigate('/');
    }, [navigate]);

    const goResults = useCallback((sub: ResultsSubTab) => {
        setTopTab('results');
        setResultsSubTab(sub);
    }, []);
    const goRun = useCallback((sub: RunSubTab) => {
        setTopTab('run');
        setRunSubTab(sub);
    }, []);

    useKeyboardShortcuts(
        {
            escape: () => setSelectedColumn(null),
            '1': () => goResults('overview'),
            '2': () => goResults('visual'),
            '3': () => goResults('code'),
            '4': () => goResults('data'),
            '5': () => goRun('logs'),
            '6': () => goRun('events'),
            'cmd+enter': handleRerun,
            'ctrl+enter': handleRerun,
        },
        { enabled: true },
    );

    const codeStreaming = !isCompleted;
    const resultsTabsWithBadges: PreviewTabDef<ResultsSubTab>[] = RESULTS_TABS.map((t) => {
        if (t.id === 'code') {
            return {
                ...t,
                badge: (
                    <span
                        className={`inline-flex items-center gap-1 px-1 py-px text-[11px] uppercase tracking-[0.04em] rounded ${
                            codeStreaming
                                ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
                                : 'bg-[rgba(52,211,153,0.12)] text-[var(--ok)]'
                        }`}
                    >
                        <span
                            className={`inline-block w-1.5 h-1.5 rounded-full ${codeStreaming ? 'animate-pulse' : ''}`}
                            style={{
                                backgroundColor: codeStreaming
                                    ? 'var(--accent)'
                                    : 'var(--ok)',
                            }}
                        />
                        {codeStreaming ? 'streaming' : 'ready'}
                    </span>
                ),
            };
        }
        return t;
    });

    const runTabsWithBadges: PreviewTabDef<RunSubTab>[] = RUN_TABS.map((t) => {
        if (t.id === 'events' && events.length > 0) {
            return {
                ...t,
                badge: (
                    <span className="inline-flex items-center px-1 py-px text-[11px] font-mono rounded bg-[rgba(255,255,255,0.06)] text-[var(--text-secondary)]">
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

            <div className="flex-1 min-h-0 min-w-0 border border-[var(--rule)] rounded-lg bg-[var(--surface-1)] overflow-hidden flex flex-col">
                {/* Top-level tabs — bigger, bolder than the sub-tabs underneath. */}
                <div
                    role="tablist"
                    aria-label="Command center sections"
                    className="shrink-0 flex items-center gap-1 px-3 pt-2 border-b border-[var(--rule)]"
                >
                    <TopTabButton
                        label="Results"
                        active={topTab === 'results'}
                        onClick={() => setTopTab('results')}
                    />
                    <TopTabButton
                        label="Run"
                        active={topTab === 'run'}
                        onClick={() => setTopTab('run')}
                        badge={
                            events.length > 0 ? (
                                <span className="inline-flex items-center px-1 py-px text-[11px] font-mono rounded bg-[rgba(255,255,255,0.06)] text-[var(--text-secondary)]">
                                    {events.length}
                                </span>
                            ) : null
                        }
                    />
                </div>

                {/* Both top-level groups render with `hidden` rather than a ternary
                    so each group keeps its sub-tab scroll position when the user
                    cycles Results → Run → Results. */}
                <div className="flex-1 min-h-0 min-w-0 relative">
                    <div className="absolute inset-0" hidden={topTab !== 'results'}>
                        <PreviewTabs
                            tabs={resultsTabsWithBadges}
                            activeTab={resultsSubTab}
                            onChange={setResultsSubTab}
                        >
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
                            }}
                        </PreviewTabs>
                    </div>
                    <div className="absolute inset-0" hidden={topTab !== 'run'}>
                        <PreviewTabs
                            tabs={runTabsWithBadges}
                            activeTab={runSubTab}
                            onChange={setRunSubTab}
                        >
                            {{
                                logs: <LogsPanel logs={logs} />,
                                events: (
                                    <div className="h-full p-2">
                                        <EventStream events={events} />
                                    </div>
                                ),
                            }}
                        </PreviewTabs>
                    </div>
                </div>
            </div>

            <StatusBar isConnected={isConnected} phases={phases} />
        </div>
    );
};

interface TopTabButtonProps {
    label: string;
    active: boolean;
    onClick: () => void;
    badge?: ReactNode;
}

const TopTabButton: FC<TopTabButtonProps> = ({ label, active, onClick, badge }) => (
    <button
        type="button"
        role="tab"
        aria-selected={active}
        onClick={onClick}
        className={`px-4 py-2 text-[14px] font-semibold rounded-t-md transition-colors flex items-center gap-1.5 ${
            active
                ? 'bg-[var(--surface-2)] text-[var(--text-primary)]'
                : 'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
        }`}
    >
        <span>{label}</span>
        {badge}
    </button>
);
