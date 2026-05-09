import React from 'react';
import { JobSummary } from '../api';
import { Calendar, Loader2, Inbox, Zap } from 'lucide-react';
import { getFileName, formatRelativeTime } from '../utils/formatters';

interface JobHistoryProps {
    jobs: JobSummary[];
    onSelectJob: (jobId: string) => void;
    activeJobId: string | null;
    onUpgradeJob: (job: JobSummary) => void;
    isLoading?: boolean;
}

const STATUS_DOT_COLOR: Record<string, string> = {
    completed: 'var(--ok)',
    running: 'var(--accent)',
    pending: 'var(--accent)',
    failed: 'var(--bad)',
    cancelled: 'var(--text-dim)',
};

export const JobHistory: React.FC<JobHistoryProps> = ({ jobs, onSelectJob, activeJobId, onUpgradeJob, isLoading = false }) => {

    if (isLoading) {
        return (
            <div className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
                <Loader2 size={24} className="animate-spin" />
                <span className="text-[12px]">Loading jobs...</span>
            </div>
        );
    }

    if (jobs.length === 0) {
        return (
            <div className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
                <Inbox size={28} className="opacity-50" />
                <span className="text-[13px]">No analysis jobs yet</span>
                <span className="text-[12px] opacity-60">Start a new analysis to see it here</span>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto">
            <h3 className="mb-4 flex items-center gap-2 text-[14px]">
                <Calendar size={16} /> History
            </h3>
            <div className="flex flex-col gap-2">
                {jobs.map((job) => {
                    const isActive = activeJobId === job.id;
                    const statusColor = STATUS_DOT_COLOR[job.status.toLowerCase()] ?? 'var(--text-dim)';
                    const fullTimestamp = new Date(job.created_at).toLocaleString();
                    return (
                        <button
                            key={job.id}
                            onClick={() => onSelectJob(job.id)}
                            type="button"
                            aria-label={`Select job ${job.id}`}
                            className={`group p-3 rounded-md border w-full text-left text-inherit appearance-none block cursor-pointer transition-all duration-200 ${
                                isActive ? 'border-[var(--accent)] bg-[var(--surface-2)]' : 'border-[var(--rule)] bg-white/[0.03] hover:bg-white/[0.06]'
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <span
                                    className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                                    style={{ backgroundColor: statusColor }}
                                    aria-label={`status: ${job.status}`}
                                />
                                <span
                                    className="text-[14px] font-medium text-[var(--text-primary)] truncate"
                                    title={job.csv_path}
                                >
                                    {getFileName(job.csv_path)}
                                </span>
                            </div>
                            <div className="text-[12px] text-[var(--text-secondary)] flex items-center gap-2">
                                <span className="capitalize">{job.mode}</span>
                                <span className="text-[var(--text-dim)]">·</span>
                                <span title={fullTimestamp}>
                                    {formatRelativeTime(job.created_at)}
                                </span>
                            </div>

                            {/* Hover/active reveals tokens, cost, and the upgrade button. */}
                            <div className={`mt-2 flex items-center gap-2 text-[11px] text-[var(--text-secondary)] ${
                                isActive ? 'flex' : 'hidden group-hover:flex'
                            }`}>
                                {job.token_usage?.total !== undefined && (
                                    <span className="bg-white/10 px-1.5 py-px rounded-sm font-mono">
                                        {job.token_usage.total.toLocaleString()} tks
                                    </span>
                                )}
                                {job.cost_estimate && (
                                    <span className="font-mono">
                                        ${job.cost_estimate.total?.toFixed(4) || '0.000'}
                                    </span>
                                )}
                                {job.status === 'completed' && job.mode === 'exploratory' && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onUpgradeJob(job);
                                        }}
                                        title="Upgrade to Predictive using Cached Profile"
                                        className="ml-auto bg-transparent border border-[var(--accent)] text-[var(--accent)] rounded-sm px-1.5 py-px text-[11px] cursor-pointer font-semibold hover:bg-[var(--accent-soft)] flex items-center gap-1"
                                    >
                                        <Zap size={12} />
                                        Upgrade
                                    </button>
                                )}
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
