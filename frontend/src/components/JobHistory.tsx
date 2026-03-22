import React from 'react';
import { JobSummary } from '../api';
import { Calendar, CheckCircle, XCircle, PlayCircle, AlertCircle, Clock, Loader2, Inbox } from 'lucide-react';
import { getFileName } from '../utils/formatters';

interface JobHistoryProps {
    jobs: JobSummary[];
    onSelectJob: (jobId: string) => void;
    activeJobId: string | null;
    onUpgradeJob: (job: JobSummary) => void;
    isLoading?: boolean;
}

export const JobHistory: React.FC<JobHistoryProps> = ({ jobs, onSelectJob, activeJobId, onUpgradeJob, isLoading = false }) => {

    const getStatusIcon = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed': return <CheckCircle size={16} color="#68d391" />;
            case 'running': return <PlayCircle size={16} color="#63b3ed" />;
            case 'failed': return <XCircle size={16} color="#fc8181" />;
            case 'cancelled': return <AlertCircle size={16} color="#a0aec0" />;
            default: return <Clock size={16} color="#a0aec0" />;
        }
    };

    if (isLoading) {
        return (
            <div className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
                <Loader2 size={24} className="animate-spin" />
                <span className="text-[0.85rem]">Loading jobs...</span>
            </div>
        );
    }

    if (jobs.length === 0) {
        return (
            <div className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
                <Inbox size={28} className="opacity-50" />
                <span className="text-[0.85rem]">No analysis jobs yet</span>
                <span className="text-[0.8rem] opacity-60">Start a new analysis to see it here</span>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto">
            <h3 className="mb-4 flex items-center gap-2 text-[0.9rem]">
                <Calendar size={16} /> History
            </h3>
            <div className="flex flex-col gap-2">
                {jobs.map((job) => (
                    <button
                        key={job.id}
                        onClick={() => onSelectJob(job.id)}
                        type="button"
                        aria-label={`Select job ${job.id}`}
                        className={`p-3 rounded-md border w-full text-left text-inherit appearance-none block cursor-pointer transition-all duration-200 ${
                            activeJobId === job.id
                                ? 'border-[var(--bg-sky-aqua)] bg-[var(--bg-french-blue)]'
                                : 'border-[var(--border-color)] bg-white/[0.03] hover:bg-white/[0.06]'
                        }`}
                    >
                        <div className="flex justify-between items-center mb-1">
                            <span className="font-medium text-[0.9rem] text-[var(--text-primary)]">{job.mode} Analysis</span>
                            {getStatusIcon(job.status)}
                        </div>

                        {/* Filename Display */}
                        <div className="text-[0.8rem] text-[var(--text-secondary)] mb-1 font-medium overflow-hidden text-ellipsis whitespace-nowrap" title={job.csv_path}>
                            {getFileName(job.csv_path)}
                        </div>

                        <div className="text-[0.8rem] text-[var(--text-secondary)] flex justify-between items-center">
                            <span>{new Date(job.created_at).toLocaleString()}</span>
                            <div className="flex gap-2 items-center">
                                {job.token_usage?.total !== undefined && (
                                    <span className="text-[0.75rem] bg-white/10 px-1 py-px rounded-sm">
                                        {job.token_usage.total.toLocaleString()} tks
                                    </span>
                                )}
                                {job.cost_estimate && (
                                    <span>${job.cost_estimate.total?.toFixed(4) || '0.000'}</span>
                                )}
                            </div>
                        </div>
                        <div className="text-[0.75rem] text-white/40 mt-1 font-mono flex justify-between items-center">
                            <span>ID: {job.id.slice(0, 8)}</span>
                            {job.status === 'completed' && job.mode === 'exploratory' && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onUpgradeJob(job);
                                    }}
                                    title="Upgrade to Predictive using Cached Profile"
                                    className="bg-transparent border border-[var(--bg-blue-green)] text-[var(--bg-blue-green)] rounded-sm px-1.5 py-px text-[0.7rem] cursor-pointer font-semibold hover:bg-[rgba(56,161,105,0.1)]"
                                >
                                    UPGRADE ⚡
                                </button>
                            )}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
};
