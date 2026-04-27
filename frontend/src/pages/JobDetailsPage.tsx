
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useJobContext } from '../context/JobContext';
import { LogViewer } from '../components/LogViewer';
import { NotebookViewer } from '../components/NotebookViewer';
import { DataOverview } from '../components/DataOverview';
import { AgentTrace } from '../components/AgentTrace';
import { ErrorState } from '../components/ErrorState';
import { CommandCenterView } from '../components/command-center/CommandCenterView';
import { featureFlags } from '../featureFlags';
import { Clock } from 'lucide-react';
import { STATUS_STYLES } from '../constants/statusStyles';

const TABS = [
    { id: 'status' as const, label: 'Status' },
    { id: 'logs' as const, label: 'Logs' },
    { id: 'notebook' as const, label: 'Notebook' },
    { id: 'data' as const, label: 'Data Overview' },
];

export const JobDetailsPage: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();
    const {
        jobs,
        setActiveJobId,
        logs,
        events,
        progress,
        handleCancelJob
    } = useJobContext();

    const [activeTab, setActiveTab] = useState<'status' | 'logs' | 'notebook' | 'data'>('status');

    useEffect(() => {
        if (jobId) {
            setActiveJobId(jobId);
        }
    }, [jobId, setActiveJobId]);

    const selectedJob = jobs.find(j => j.id === jobId);

    if (!selectedJob) {
        return (
            <div className="text-[var(--text-secondary)] p-8 flex items-center gap-3">
                <Clock size={20} className="animate-spin" />
                Loading job details...
            </div>
        );
    }

    const displayStatus = selectedJob.status;
    const statusStyle = STATUS_STYLES[displayStatus] || STATUS_STYLES.cancelled;

    // Command Center surface — gated by VITE_FEATURE_COMMAND_CENTER. Falls back
    // to the legacy tabs layout below when the flag is off so rollback is a
    // one-line env change.
    if (featureFlags.commandCenter) {
        return <CommandCenterView job={selectedJob} />;
    }

    return (
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
            {/* Tabs with ARIA */}
            <div
                role="tablist"
                aria-label="Job details tabs"
                className="shrink-0 flex gap-1 mb-4 border-b border-[var(--border-color)]"
            >
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        role="tab"
                        aria-selected={activeTab === tab.id}
                        aria-controls={`tabpanel-${tab.id}`}
                        id={`tab-${tab.id}`}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-[1.1rem] py-[0.6rem] bg-transparent border-none border-b-2 border-solid cursor-pointer transition-[color,border-color] duration-200 text-[0.9rem] ${
                            activeTab === tab.id
                                ? 'border-b-[var(--bg-turquoise-surf)] text-[var(--bg-turquoise-surf)] font-semibold'
                                : 'border-b-transparent text-[var(--text-secondary)] font-medium'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content Area with fade transition */}
            <div className="flex-1 min-h-0 min-w-0 flex flex-col">

                <div
                    role="tabpanel"
                    id={`tabpanel-${activeTab}`}
                    aria-labelledby={`tab-${activeTab}`}
                    className="flex-1 flex flex-col min-h-0 animate-[fadeIn_0.2s_ease-out]"
                >
                    {activeTab === 'status' && (
                        <div className="flex-1 p-6 border border-[var(--border-color)] rounded-xl bg-[var(--bg-true-cobalt)] overflow-auto">
                            <h4 className="m-0 mb-4 text-[1.1rem] text-[var(--text-primary)]">Current Job Monitor</h4>
                            <div className="flex items-center gap-2 mb-6 p-3 bg-[rgba(0,0,0,0.2)] rounded-md">
                                <span className="text-[var(--text-secondary)] text-[0.9rem]">ID:</span>
                                <span className="font-mono font-semibold">{selectedJob.id.slice(0, 8)}...</span>
                                <div className="flex-1" />
                                <span className={`px-[10px] py-[2px] rounded text-[0.8rem] font-bold uppercase tracking-[0.03em] ${statusStyle.bg} ${statusStyle.color}`}>
                                    {displayStatus}
                                </span>
                            </div>

                            {displayStatus === 'failed' ? (
                                <ErrorState
                                    title="Analysis Failed"
                                    message={logs.length > 0 ? logs[logs.length - 1].message : "An unexpected error occurred during analysis."}
                                    suggestions={["Check the logs for detailed error messages.", "Ensure your data file is correctly formatted.", "Try a different analysis mode."]}
                                    onRetry={() => window.location.reload()}
                                    onViewLogs={() => setActiveTab('logs')}
                                    onTryDifferentMode={() => navigate('/')}
                                />
                            ) : (
                                <AgentTrace
                                    status={displayStatus}
                                    mode={selectedJob.mode || 'exploratory'}
                                    logs={logs.map(l => l.message)}
                                    events={events}
                                    progress={progress}
                                />
                            )}

                            {displayStatus === 'running' && (
                                <button
                                    onClick={handleCancelJob}
                                    className="w-full p-3 bg-[rgba(245,101,101,0.1)] text-[#fc8181] border border-[rgba(245,101,101,0.3)] rounded-md cursor-pointer font-semibold transition-all duration-200 mt-4 hover:bg-[rgba(245,101,101,0.2)]"
                                >
                                    Cancel Job
                                </button>
                            )}
                        </div>
                    )}

                    {activeTab === 'logs' && <LogViewer logs={logs} />}

                    {activeTab === 'notebook' && (
                        <NotebookViewer
                            jobId={selectedJob.id}
                            resultPath={selectedJob.result_path ?? null}
                            status={selectedJob.status}
                            mode={selectedJob.mode}
                        />
                    )}

                    {activeTab === 'data' && (
                        <div className="flex-1 flex flex-col border border-[var(--border-color)] rounded-xl bg-[var(--bg-true-cobalt)] overflow-hidden min-w-0">
                            <DataOverview jobId={selectedJob.id} />
                        </div>
                    )}
                </div>
            </div>

            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(4px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    );
};
