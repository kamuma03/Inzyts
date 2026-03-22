import React from 'react';
import { AlertTriangle, RefreshCcw, FileText, ArrowRight } from 'lucide-react';

interface ErrorStateProps {
    title: string;
    message: string;
    suggestions: string[];
    onRetry?: () => void;
    onViewLogs?: () => void;
    onTryDifferentMode?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
    title = "Analysis Failed",
    message,
    suggestions = [],
    onRetry,
    onViewLogs,
    onTryDifferentMode
}) => {
    return (
        <div className="p-6 bg-[rgba(245,101,101,0.08)] border border-[rgba(245,101,101,0.3)] rounded-lg text-[#fc8181]">
            <div className="flex items-center gap-3 mb-4">
                <AlertTriangle size={24} />
                <h3 className="m-0 text-[1.1rem] font-bold">{title}</h3>
            </div>

            <div className="mb-6 leading-relaxed text-[#feb2b2]">
                {message}
            </div>

            {suggestions.length > 0 && (
                <div className="mb-6 bg-[rgba(0,0,0,0.2)] border border-[rgba(245,101,101,0.2)] rounded-md p-4">
                    <h4 className="mt-0 mr-0 mb-2 ml-0 text-[0.95rem] text-[#fc8181]">Suggestions:</h4>
                    <ul className="m-0 pl-6 text-[#feb2b2]">
                        {suggestions.map((suggestion, idx) => (
                            <li key={idx} className="mb-1">{suggestion}</li>
                        ))}
                    </ul>
                </div>
            )}

            <div className="flex gap-4">
                {onRetry && (
                    <button
                        onClick={onRetry}
                        className="flex items-center gap-2 px-4 py-2 bg-[rgba(245,101,101,0.2)] text-[#fc8181] border border-[rgba(245,101,101,0.4)] rounded-md font-semibold cursor-pointer transition-all duration-200 hover:bg-[rgba(245,101,101,0.3)]"
                    >
                        <RefreshCcw size={16} /> Retry Analysis
                    </button>
                )}

                {onViewLogs && (
                    <button
                        onClick={onViewLogs}
                        className="flex items-center gap-2 px-4 py-2 bg-transparent text-[var(--text-secondary)] border border-[var(--border-color)] rounded-md font-semibold cursor-pointer transition-all duration-200 hover:border-[var(--bg-turquoise-surf)] hover:text-[var(--text-primary)]"
                    >
                        <FileText size={16} /> View Logs
                    </button>
                )}

                {onTryDifferentMode && (
                    <button
                        onClick={onTryDifferentMode}
                        className="flex items-center gap-2 px-4 py-2 bg-transparent text-[var(--text-secondary)] border-none font-semibold cursor-pointer ml-auto transition-colors duration-200 hover:text-[var(--bg-turquoise-surf)]"
                    >
                        Try Different Mode <ArrowRight size={16} />
                    </button>
                )}
            </div>
        </div>
    );
};
