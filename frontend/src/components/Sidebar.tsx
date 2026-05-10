import React, { useState } from 'react';
import { JobHistory } from './JobHistory';
import { JobSummary } from '../api';
import { ChevronLeft, ChevronRight, History, Plus } from 'lucide-react';

interface SidebarProps {
    jobs: JobSummary[];
    onSelectJob: (jobId: string) => void;
    activeJobId: string | null;
    onNewAnalysis: () => void;
    onUpgradeJob: (job: JobSummary) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ jobs, onSelectJob, activeJobId, onNewAnalysis, onUpgradeJob }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <div
            className={`${isCollapsed ? 'w-[60px] min-w-[60px]' : 'w-[350px] min-w-[350px]'} transition-all duration-300 ease-in-out bg-[var(--surface-0)] border-r border-[var(--rule)] text-[var(--text-primary)] flex flex-col h-auto min-h-fit relative overflow-hidden rounded-none`}
        >
            {/* Toggle Button */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={`absolute top-3 ${isCollapsed ? 'right-1/2 translate-x-1/2' : 'right-3 translate-x-0'} bg-transparent hover:bg-[var(--surface-2)] border border-[var(--rule)] hover:border-[var(--rule-strong)] rounded-full w-7 h-7 flex items-center justify-center cursor-pointer z-10 transition-colors duration-200`}
                title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                aria-expanded={!isCollapsed}
            >
                {isCollapsed ? <ChevronRight size={16} color="var(--text-secondary)" /> : <ChevronLeft size={16} color="var(--text-secondary)" />}
            </button>

            {/* Sidebar Content */}
            <div className={`${isCollapsed ? 'opacity-0 pointer-events-none hidden' : 'opacity-100 pointer-events-auto flex'} transition-opacity duration-200 ease-in-out p-6 pt-14 flex-col h-full overflow-hidden`}>
                <button
                    onClick={onNewAnalysis}
                    aria-label="New analysis"
                    className="w-full flex items-center gap-2 px-3 py-2.5 rounded-md text-[var(--text-primary)] hover:bg-white/[0.04] text-sm font-medium border border-[var(--rule)] mb-4 transition-colors"
                >
                    <Plus size={16} />
                    <span>New analysis</span>
                </button>


                <div className="flex-1 overflow-y-auto min-h-0">
                    <JobHistory
                        jobs={jobs}
                        onSelectJob={onSelectJob}
                        activeJobId={activeJobId}
                        onUpgradeJob={onUpgradeJob}
                        onNewAnalysis={onNewAnalysis}
                    />
                </div>
            </div>

            {/* Collapsed Icons View */}
            <div className={`${isCollapsed ? 'flex opacity-100' : 'hidden opacity-0'} flex-col items-center pt-[60px] gap-5 transition-opacity duration-300 ease-in-out delay-100`}>
                <button
                    title="New analysis"
                    onClick={onNewAnalysis}
                    aria-label="New analysis"
                    className="cursor-pointer p-2 rounded-md border border-[var(--rule)] flex items-center justify-center text-[var(--text-primary)] hover:bg-white/[0.04] transition-colors"
                >
                    <Plus size={20} />
                </button>
                <div title="Job History">
                    <History size={24} color="var(--text-secondary)" />
                </div>
            </div>
        </div>
    );
};
