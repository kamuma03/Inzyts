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
            className={`${isCollapsed ? 'w-[60px] min-w-[60px]' : 'w-[350px] min-w-[350px]'} transition-all duration-300 ease-in-out bg-[var(--bg-deep-twilight)] border-r border-[var(--border-color)] text-[var(--text-primary)] flex flex-col h-auto min-h-fit relative overflow-hidden rounded-xl`}
        >
            {/* Toggle Button */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={`absolute top-3 ${isCollapsed ? 'right-1/2 translate-x-1/2' : 'right-3 translate-x-0'} bg-[var(--bg-french-blue)] border border-[var(--border-color)] rounded-full w-7 h-7 flex items-center justify-center cursor-pointer z-10 transition-all duration-300 ease-in-out`}
                title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                aria-expanded={!isCollapsed}
            >
                {isCollapsed ? <ChevronRight size={16} color="var(--text-secondary)" /> : <ChevronLeft size={16} color="var(--text-secondary)" />}
            </button>

            {/* Sidebar Content */}
            <div className={`${isCollapsed ? 'opacity-0 pointer-events-none hidden' : 'opacity-100 pointer-events-auto flex'} transition-opacity duration-200 ease-in-out p-6 pt-14 flex-col h-full overflow-hidden`}>
                {/* New Analysis Button (Req UI Refactor) */}
                <button
                    onClick={onNewAnalysis}
                    aria-label="New Analysis"
                    className="w-full p-4 bg-[var(--bg-blue-green)] text-white border-none rounded-lg cursor-pointer flex items-center justify-center gap-3 text-base font-bold mb-4 shadow-[0_4px_6px_rgba(0,0,0,0.2)] transition-transform duration-100 ease-in-out hover:-translate-y-0.5"
                >
                    <Plus size={20} fontWeight={800} /> NEW ANALYSIS
                </button>


                <div className="flex-1 overflow-y-auto min-h-0">
                    <JobHistory jobs={jobs} onSelectJob={onSelectJob} activeJobId={activeJobId} onUpgradeJob={onUpgradeJob} />
                </div>
            </div>

            {/* Collapsed Icons View */}
            <div className={`${isCollapsed ? 'flex opacity-100' : 'hidden opacity-0'} flex-col items-center pt-[60px] gap-5 transition-opacity duration-300 ease-in-out delay-100`}>
                <button
                    title="New Analysis"
                    onClick={onNewAnalysis}
                    aria-label="New Analysis"
                    className="cursor-pointer bg-[var(--bg-blue-green)] p-2 rounded-full border-none flex items-center justify-center"
                >
                    <Plus size={24} color="#fff" />
                </button>
                <div title="Job History">
                    <History size={24} color="var(--text-secondary)" />
                </div>
            </div>
        </div>
    );
};
