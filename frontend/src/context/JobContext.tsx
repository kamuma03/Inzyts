
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { JobSummary, AnalysisAPI, type RunMetrics, type PhaseStatus } from '../api';
import { useSocket, LogMessage, AgentEvent, ProgressUpdate } from '../hooks/useSocket';
import { ToastType, ToastProps } from '../components/Toast';
import { AnalysisFormInitialValues } from '../components/AnalysisForm';

interface JobContextType {
    // State
    jobs: JobSummary[];
    activeJobId: string | null;
    isConnected: boolean;
    logs: LogMessage[];
    events: AgentEvent[];
    progress: ProgressUpdate | null;
    metrics: RunMetrics | null;
    phases: PhaseStatus[] | null;
    toasts: ToastProps[];
    initialFormState: AnalysisFormInitialValues | null;

    // Actions
    setActiveJobId: (id: string | null) => void;
    fetchJobs: () => Promise<void>;
    handleJobCreated: (jobId: string) => void;
    handlePlayJob: (jobId: string) => void; // For playing/selecting a job
    handleUpgradeJob: (job: JobSummary) => void;
    handleCancelJob: () => Promise<void>;
    addToast: (message: string, type?: ToastType) => void;
    removeToast: (id: string) => void;
    clearInitialFormState: () => void;
}

const JobContext = createContext<JobContextType | undefined>(undefined);

export const useJobContext = () => {
    const context = useContext(JobContext);
    if (!context) {
        throw new Error('useJobContext must be used within a JobProvider');
    }
    return context;
};

interface JobProviderProps {
    children: ReactNode;
}

export const JobProvider: React.FC<JobProviderProps> = ({ children }) => {
    // -- State --
    const [jobs, setJobs] = useState<JobSummary[]>([]);
    const [activeJobId, setActiveJobId] = useState<string | null>(null);
    const [initialFormState, setInitialFormState] = useState<AnalysisFormInitialValues | null>(null);
    const [toasts, setToasts] = useState<ToastProps[]>([]);
    const [historicalLogs, setHistoricalLogs] = useState<LogMessage[]>([]);

    // Socket Hook
    const { logs, events, progress, metrics, phases, isConnected } = useSocket(activeJobId);

    // -- Toast Logic --
    const addToast = (message: string, type: ToastType = 'info') => {
        // eslint-disable-next-line react-hooks/purity
        const id = Math.random().toString(36).substr(2, 9);
        setToasts(prev => [...prev, { id, message, type, onClose: removeToast }]);
        // Auto remove after 5s? The original code didn't seem to have auto-remove timer in addToast but relies on Toast component?
        // Let's keep it simple as per original
    };

    const removeToast = (id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    };

    // -- Job Logic --
    const fetchJobs = async () => {
        try {
            const data = await AnalysisAPI.getJobs();
            setJobs(data);
        } catch (error) {
            if (import.meta.env.DEV) console.error('Failed to fetch jobs', error);
            // Avoid spamming toasts on polling failure
        }
    };

    useEffect(() => {
        let timeoutId: NodeJS.Timeout;

        const pool = async () => {
            await fetchJobs();

            // If we have an active job, poll it faster
            if (activeJobId) {
                try {
                    const statusData = await AnalysisAPI.getJobStatus(activeJobId);

                    // Update jobs list with latest status
                    setJobs(prevJobs => prevJobs.map(job =>
                        job.id === activeJobId ? {
                            ...job,
                            status: statusData.status,
                            result_path: statusData.result_path,
                            error_message: statusData.error
                        } : job
                    ));

                    // Update historical logs from API
                    if (statusData.logs && Array.isArray(statusData.logs)) {
                        setHistoricalLogs(statusData.logs);
                    }

                    if (['completed', 'failed', 'cancelled'].includes(statusData.status)) {
                        // Job finished, back to slow poll (implied by not scheduling fast poll)
                        timeoutId = setTimeout(pool, 5000);
                    } else {
                        // Job still running, poll again soon
                        timeoutId = setTimeout(pool, 2000);
                    }
                } catch (e) {
                    console.error("Fast poll failed", e);
                    timeoutId = setTimeout(pool, 5000);
                }
            } else {
                timeoutId = setTimeout(pool, 5000);
            }
        };

        pool();
        return () => clearTimeout(timeoutId);
    }, [activeJobId]);

    // Computed merged logs
    const mergedLogs = React.useMemo(() => {
        const uniqueLogs = new Map<string, LogMessage>();

        // Add historical first
        historicalLogs.forEach((l, index) => {
            // Create a unique key. Fallback to index+message if timestamp missing to prevent collapsing distinct logs.
            const key = l.timestamp ? `${l.timestamp}-${l.message}` : `hist-${index}-${l.message}`;
            uniqueLogs.set(key, l);
        });

        // Add socket logs (newer/realtime)
        logs.forEach((l, index) => {
            const key = l.timestamp ? `${l.timestamp}-${l.message}` : `sock-${index}-${l.message}`;
            if (!uniqueLogs.has(key)) {
                uniqueLogs.set(key, l);
            }
        });

        // Convert to array and sort by timestamp
        return Array.from(uniqueLogs.values()).sort((a, b) => {
            const tA = new Date(a.timestamp).getTime();
            const tB = new Date(b.timestamp).getTime();
            return tA - tB;
        });
    }, [historicalLogs, logs]);


    // -- Actions --
    const handleJobCreated = (jobId: string) => {
        setActiveJobId(jobId);
        fetchJobs();
        addToast('Analysis job started', 'info');
    };

    const handlePlayJob = (jobId: string) => {
        setActiveJobId(jobId);
        // Additional logic for "playing" if needed
    };

    const handleUpgradeJob = (job: JobSummary) => {
        setInitialFormState({
            manualPath: job.csv_path || '',
            mode: 'predictive',
            use_cache: true
        });
        addToast("Upgrade mode: Form pre-filled for Predictive Analysis", "info");
    };

    const handleCancelJob = async () => {
        if (activeJobId) {
            try {
                await AnalysisAPI.cancelJob(activeJobId);
                fetchJobs();
                addToast('Job cancelled', 'info');
            } catch (e) {
                addToast('Failed to cancel job', 'error');
            }
        }
    };

    const clearInitialFormState = () => {
        setInitialFormState(null);
    }

    const value: JobContextType = {
        jobs,
        activeJobId,
        isConnected,
        logs: mergedLogs, // Expose the merged logs instead of just socket logs
        events,
        progress,
        metrics,
        phases,
        toasts,
        initialFormState,
        setActiveJobId,
        fetchJobs,
        handleJobCreated,
        handlePlayJob,
        handleUpgradeJob,
        handleCancelJob,
        addToast,
        removeToast,
        clearInitialFormState
    };

    return (
        <JobContext.Provider value={value}>
            {children}
        </JobContext.Provider>
    );
};
