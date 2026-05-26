import { useCallback, useState, type FC, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JobSummary } from '../../api';
import { useJobContext } from '../../context/JobContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useMetricsHistory } from '../../hooks/useRunMetrics';
import { TopStrip } from './TopStrip';
import {
    PreviewTabBar,
    PreviewTabPanels,
    type PreviewTabId,
    type PreviewTabDef,
} from './PreviewTabs';
import { OverviewPanel } from './panels/OverviewPanel';
import { NotebookPanel } from './panels/NotebookPanel';
import { ReportPanel } from './panels/ReportPanel';
import { DataPanel } from './panels/DataPanel';
import { LogsPanel } from './panels/LogsPanel';
import { TrafficRow } from './TrafficRow';
import { EventStream } from './EventStream';
import { StatusBar } from './StatusBar';

interface CommandCenterViewProps {
    job: JobSummary;
}

type TopTab = 'results' | 'run';
type ResultsSubTab = Extract<PreviewTabId, 'overview' | 'data' | 'report' | 'notebook'>;
type RunSubTab = Extract<PreviewTabId, 'logs' | 'events'>;

const RESULTS_TABS: { id: ResultsSubTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'data', label: 'Data' },
    { id: 'report', label: 'Report' },
    { id: 'notebook', label: 'Notebook' },
];

const RUN_TABS: { id: RunSubTab; label: string }[] = [
    { id: 'logs', label: 'Logs' },
    { id: 'events', label: 'Events' },
];

const DEFAULT_RESULTS_TAB_FOR_STATUS = (status: string): ResultsSubTab =>
    status === 'completed' ? 'report' : 'overview';

/** Top-level analyst surface. Two top-level groups ("Results" and "Run")
 *  split the original six tabs into "what came out" vs "how it ran".
 *
 *  The chrome row inlines a Results/Run segmented control alongside the
 *  active group's sub-tabs so we render one strip total instead of two
 *  stacked strips. The Run group still surfaces its events count via a
 *  badge on the segmented control.
 *
 *  Each top-level group keeps its own active sub-tab in state so cycling
 *  between them feels stateful, and panels for both groups render
 *  side-by-side toggled with `hidden` so scroll position is preserved
 *  when the user switches groups. */
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
            '2': () => goResults('data'),
            '3': () => goResults('report'),
            '4': () => goResults('notebook'),
            '5': () => goRun('logs'),
            '6': () => goRun('events'),
            'cmd+enter': handleRerun,
            'ctrl+enter': handleRerun,
        },
        { enabled: true },
    );

    const notebookStreaming = !isCompleted;
    const resultsTabsWithBadges: PreviewTabDef<ResultsSubTab>[] = RESULTS_TABS.map((t) => {
        if (t.id === 'notebook' && notebookStreaming) {
            return {
                ...t,
                badge: (
                    <span className="inline-flex items-center gap-1 px-1 py-px text-[11px] uppercase tracking-[0.04em] rounded bg-[var(--accent-soft)] text-[var(--accent)]">
                        <span
                            className="inline-block w-1.5 h-1.5 rounded-full animate-pulse"
                            style={{ backgroundColor: 'var(--accent)' }}
                        />
                        streaming
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

    const groupSwitcher = (
        <GroupSwitcher
            topTab={topTab}
            onSelect={setTopTab}
            runBadge={events.length > 0 ? events.length : null}
        />
    );

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
                {/* Single combined chrome row — segmented pill on the left,
                    the active group's sub-tabs flowing right of it. */}
                {topTab === 'results' ? (
                    <PreviewTabBar
                        tabs={resultsTabsWithBadges}
                        activeTab={resultsSubTab}
                        onChange={setResultsSubTab}
                        ariaLabel="Results sub-tabs"
                        prefix={groupSwitcher}
                    />
                ) : (
                    <PreviewTabBar
                        tabs={runTabsWithBadges}
                        activeTab={runSubTab}
                        onChange={setRunSubTab}
                        ariaLabel="Run sub-tabs"
                        prefix={groupSwitcher}
                    />
                )}

                {/* Panels area — both groups render with `hidden` so each
                    group keeps its sub-tab scroll position across cycles. */}
                <div className="flex-1 min-h-0 min-w-0 relative">
                    <div className="absolute inset-0 flex flex-col" hidden={topTab !== 'results'}>
                        <PreviewTabPanels
                            tabs={resultsTabsWithBadges}
                            activeTab={resultsSubTab}
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
                                data: <DataPanel jobId={job.id} />,
                                report: <ReportPanel job={job} />,
                                notebook: <NotebookPanel job={job} events={events} />,
                            }}
                        </PreviewTabPanels>
                    </div>
                    <div className="absolute inset-0 flex flex-col" hidden={topTab !== 'run'}>
                        <PreviewTabPanels
                            tabs={runTabsWithBadges}
                            activeTab={runSubTab}
                        >
                            {{
                                logs: <LogsPanel logs={logs} />,
                                events: (
                                    <div className="h-full p-2">
                                        <EventStream events={events} />
                                    </div>
                                ),
                            }}
                        </PreviewTabPanels>
                    </div>
                </div>
            </div>

            <StatusBar isConnected={isConnected} phases={phases} />
        </div>
    );
};

interface GroupSwitcherProps {
    topTab: TopTab;
    onSelect: (id: TopTab) => void;
    runBadge?: ReactNode;
}

/** Compact segmented control for Results / Run. Renders inline as a prefix
 *  in the sub-tab strip, separated by a vertical hairline. */
const GroupSwitcher: FC<GroupSwitcherProps> = ({ topTab, onSelect, runBadge }) => (
    <>
        <div
            role="tablist"
            aria-label="Command center sections"
            className="flex items-center p-0.5 rounded-md bg-[rgba(0,0,0,0.25)] mr-2"
        >
            <SegmentedButton
                label="Results"
                active={topTab === 'results'}
                onClick={() => onSelect('results')}
            />
            <SegmentedButton
                label="Run"
                active={topTab === 'run'}
                onClick={() => onSelect('run')}
                badge={runBadge}
            />
        </div>
        <span className="w-px h-4 bg-[var(--rule)] mr-2" aria-hidden="true" />
    </>
);

interface SegmentedButtonProps {
    label: string;
    active: boolean;
    onClick: () => void;
    badge?: ReactNode;
}

const SegmentedButton: FC<SegmentedButtonProps> = ({ label, active, onClick, badge }) => (
    <button
        type="button"
        role="tab"
        aria-selected={active}
        onClick={onClick}
        className={`px-2.5 py-1 text-[12px] font-semibold rounded transition-colors flex items-center gap-1.5 ${
            active
                ? 'bg-[var(--surface-2)] text-[var(--text-primary)]'
                : 'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
        }`}
    >
        <span>{label}</span>
        {badge != null && (
            <span className="inline-flex items-center px-1 py-px text-[10px] font-mono rounded bg-[rgba(255,255,255,0.08)] text-[var(--text-secondary)]">
                {badge}
            </span>
        )}
    </button>
);
