import React, { useState } from 'react';
import { JobSummary } from '../api';
import { Database, CheckCircle, Circle, ChevronLeft, ChevronRight, Info, FileJson } from 'lucide-react';

interface ContextPanelProps {
    selectedJob: JobSummary | undefined;
    isConnected: boolean;
    onShowTemplates: () => void;
}

export const ContextPanel: React.FC<ContextPanelProps> = ({ selectedJob, isConnected, onShowTemplates }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <div
            className={`border-l border-[var(--border-color)] bg-[var(--bg-deep-twilight)] flex flex-col h-full relative transition-all duration-300 ${
                isCollapsed ? 'w-[60px] min-w-[60px] py-6 px-0 items-center' : 'w-[300px] min-w-[300px] p-6 items-stretch'
            }`}
        >
            {/* Toggle Button */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={`absolute top-3 z-10 w-7 h-7 flex items-center justify-center cursor-pointer bg-[var(--bg-french-blue)] border border-[var(--border-color)] rounded-full transition-all duration-300 ${
                    isCollapsed ? 'left-1/2 -translate-x-1/2' : 'left-3 translate-x-0'
                }`}
                title={isCollapsed ? "Expand Context" : "Collapse Context"}
            >
                {isCollapsed ? <ChevronLeft size={16} color="var(--text-secondary)" /> : <ChevronRight size={16} color="var(--text-secondary)" />}
            </button>

            {/* Main Content */}
            <div className={`flex-col h-full mt-4 ${isCollapsed ? 'hidden' : 'flex'}`}>
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-[0.75rem] font-bold uppercase tracking-wider text-[var(--text-secondary)] m-0 flex items-center gap-2 ml-8">
                        Context
                    </h3>
                    <div
                        className={`w-2 h-2 rounded-full ${isConnected ? 'bg-[var(--bg-blue-green)]' : 'bg-red-500'}`}
                        title={isConnected ? "Connected" : "Disconnected"}
                    />
                </div>

                {/* Model Section */}
                <div className="mb-8">
                    <label className="text-[0.8rem] text-[var(--text-secondary)] font-semibold block mb-2">MODEL</label>
                    <div className="px-3 py-2 bg-white/5 border border-[var(--border-color)] rounded-md text-[var(--text-primary)] text-[0.9rem]">
                        <span>{import.meta.env.VITE_LLM_MODEL || 'claude-sonnet-4-5-20250929'}</span>
                    </div>
                </div>

                <div className="h-px bg-[var(--border-color)] mb-6" />

                {/* Templates */}
                <div className="mb-8">
                    <button
                        onClick={onShowTemplates}
                        className="w-full bg-[var(--bg-deep-twilight)] border border-[var(--border-color)] rounded-md text-[var(--text-secondary)] cursor-pointer p-2 flex items-center justify-center gap-2 text-[0.85rem] font-medium transition-all duration-200 hover:border-[var(--bg-turquoise-surf)] hover:text-[var(--text-primary)] hover:bg-[rgba(79,209,197,0.1)]"
                    >
                        <FileJson size={14} />
                        <span>Manage Templates</span>
                    </button>
                </div>

                <div className="h-px bg-[var(--border-color)] mb-6" />

                {/* Data Context */}
                <div className="mb-8">
                    <label className="text-[0.8rem] text-[var(--text-secondary)] font-semibold block mb-2">DATA IN CONTEXT</label>
                    {selectedJob && selectedJob.csv_path ? (
                        <div className="flex items-center gap-3">
                            <Database size={16} color="var(--bg-blue-green)" />
                            <div>
                                <div className="text-[var(--text-primary)] text-[0.9rem] font-medium">
                                    {selectedJob.csv_path.split('/').pop()}
                                </div>
                                <div className="text-[var(--text-secondary)] text-[0.8rem]">
                                    {selectedJob.csv_path.endsWith('.parquet') ? 'Parquet' : 'CSV'}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="italic text-[var(--text-secondary)] text-[0.9rem]">None selected</div>
                    )}
                </div>

                <div className="h-px bg-[var(--border-color)] mb-6" />

                {/* Cache Status */}
                <div>
                    <label className="text-[0.8rem] text-[var(--text-secondary)] font-semibold block mb-2">CACHE STATUS</label>
                    <div className="bg-white/[0.03] rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                            <CheckCircle size={14} color="var(--bg-blue-green)" />
                            <span className="text-[var(--text-primary)] text-[0.9rem]">Base Profile</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Circle size={14} color="var(--text-secondary)" />
                            <span className="text-[var(--text-secondary)] text-[0.9rem]">Extensions</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Collapsed Icons View */}
            <div className={`flex-col items-center pt-[60px] gap-5 transition-opacity duration-300 delay-100 ${
                isCollapsed ? 'flex opacity-100' : 'hidden opacity-0'
            }`}>
                <div title="Context">
                    <Info size={24} color="var(--text-secondary)" />
                </div>
                {selectedJob && selectedJob.csv_path && (
                    <div title="Data Loaded">
                        <Database size={24} color="var(--bg-blue-green)" />
                    </div>
                )}
            </div>
        </div>
    );
};
