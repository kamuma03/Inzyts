import React from 'react';
import { JobSummary } from '../api';
import { Calendar, Zap } from 'lucide-react';
import { getFileName, formatRelativeTime } from '../utils/formatters';
import { SkeletonList, EmptyState } from './state';

interface JobHistoryProps {
    jobs: JobSummary[];
    onSelectJob: (jobId: string) => void;
    activeJobId: string | null;
    onUpgradeJob: (job: JobSummary) => void;
    isLoading?: boolean;
    /** Optional — wired by the consuming layout to its "new analysis" handler.
     *  When present, the empty-state surfaces a CTA pointing at it. */
    onNewAnalysis?: () => void;
}

const STATUS_DOT_COLOR: Record<string, string> = {
    completed: 'var(--ok)',
    running: 'var(--accent)',
    pending: 'var(--accent)',
    failed: 'var(--bad)',
    cancelled: 'var(--text-dim)',
};

export const JobHistory: React.FC<JobHistoryProps> = ({
    jobs, onSelectJob, activeJobId, onUpgradeJob, isLoading = false, onNewAnalysis,
}) => {

    if (isLoading) {
        return <SkeletonList rows={4} variant="job" />;
    }

    if (jobs.length === 0) {
        return (
            <EmptyState
                icon="inbox"
                title="No analyses yet"
                body="Start a new analysis to see it here."
                cta={onNewAnalysis ? { label: 'New analysis', onClick: onNewAnalysis } : undefined}
            />
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
                    const statusKey = job.status.toLowerCase();
                    const statusColor = STATUS_DOT_COLOR[statusKey] ?? 'var(--text-dim)';
                    const isLive = statusKey === 'running' || statusKey === 'pending';
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
                                    className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${isLive ? 'animate-pulse' : ''}`}
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

                            {/* Tokens / cost / upgrade — hover-revealed on pointer
                                devices, always visible on touch (which has no
                                hover state) and on the active card. The row
                                reserves its 20px slot via min-h so toggling
                                visibility doesn't change card height — the list
                                no longer jumps as the cursor moves over it. */}
                            <div className={`mt-2 flex items-center gap-2 min-h-[20px] text-[11px] text-[var(--text-secondary)] transition-opacity duration-150 ${
                                isActive
                                    ? 'opacity-100'
                                    : 'opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100'
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
