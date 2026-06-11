
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
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

/** Shallow equality on the job fields the UI renders, so a poll that returns
 *  identical data doesn't trigger a re-render of the whole provider tree. */
function jobsEqual(a: JobSummary[], b: JobSummary[]): boolean {
    if (a === b) return true;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        const x = a[i], y = b[i];
        if (
            x.id !== y.id ||
            x.status !== y.status ||
            x.result_path !== y.result_path ||
            x.error_message !== y.error_message ||
            x.title !== y.title
        ) {
            return false;
        }
    }
    return true;
}

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
    // removeToast is defined first so addToast can depend on a stable reference.
    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const addToast = useCallback((message: string, type: ToastType = 'info') => {
        // eslint-disable-next-line react-hooks/purity
        const id = Math.random().toString(36).slice(2, 11);
        setToasts(prev => [...prev, { id, message, type, onClose: removeToast }]);
    }, [removeToast]);

    // -- Job Logic --
    const fetchJobs = useCallback(async () => {
        // Skip the call entirely on the public/login surface — without a
        // token the backend returns 401, and the resulting console.error
        // trips the e2e "no console errors on login" assertion.
        if (!sessionStorage.getItem('inzyts_jwt_token')) {
            return;
        }
        try {
            const data = await AnalysisAPI.getJobs();
            // Skip the state update when nothing meaningful changed, so the
            // provider (and every consumer) doesn't re-render every poll cycle.
            setJobs(prev => jobsEqual(prev, data) ? prev : data);
        } catch (error) {
            if (import.meta.env.DEV) console.error('Failed to fetch jobs', error);
            // Avoid spamming toasts on polling failure
        }
    }, []);

    useEffect(() => {
        let timeoutId: NodeJS.Timeout;
        // Guards against an in-flight request resolving after this effect is
        // torn down (activeJobId changed / unmount): without it, a stale poll
        // could write old data into state and spawn an orphan polling loop.
        let cancelled = false;

        // Clear the previous job's logs immediately on switch so the viewer
        // doesn't briefly show the old job's history before the first poll.
        setHistoricalLogs([]);

        const pool = async () => {
            await fetchJobs();
            if (cancelled) return;

            // If we have an active job, poll it faster
            if (activeJobId) {
                try {
                    const statusData = await AnalysisAPI.getJobStatus(activeJobId);
                    if (cancelled) return;

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
                    if (cancelled) return;
                    console.error("Fast poll failed", e);
                    timeoutId = setTimeout(pool, 5000);
                }
            } else {
                timeoutId = setTimeout(pool, 5000);
            }
        };

        pool();
        return () => {
            cancelled = true;
            clearTimeout(timeoutId);
        };
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

    // Derive agent events from merged logs. The socket-only `events` array
    // doesn't replay on page reload, but the log file does — so we extract
    // the structured `[EVENT_NAME] …` markers from the log stream as the
    // source of truth and union with any live socket events that happen
    // to arrive before the corresponding log line lands.
    const mergedEvents = React.useMemo(() => {
        const EVENT_RE = /^\[([A-Z_][A-Z0-9_]*)\]\s+(.+?)(?:\s+\|\s+Context:\s*(\{.*\}))?$/;
        const derived: AgentEvent[] = [];
        for (const log of mergedLogs) {
            const m = log.message.match(EVENT_RE);
            if (!m) continue;
            const [, eventName, msg, ctx] = m;
            let agent: string | undefined;
            if (ctx) {
                const am = ctx.match(/['"]agent['"]:\s*['"]([^'"]+)['"]/);
                if (am) agent = am[1];
            }
            derived.push({
                type: 'agent_event',
                event: eventName,
                agent,
                data: { timestamp: log.timestamp, level: log.level, message: msg },
            });
        }

        // Union with live socket events, deduped by (event, agent, timestamp).
        const seen = new Set<string>();
        const out: AgentEvent[] = [];
        for (const e of [...derived, ...events]) {
            const ts = (e.data as { timestamp?: string } | undefined)?.timestamp ?? '';
            const key = `${e.event}:${e.agent ?? ''}:${ts}`;
            if (seen.has(key)) continue;
            seen.add(key);
            out.push(e);
        }
        return out;
    }, [mergedLogs, events]);


    // -- Actions (stable references so the memoized value doesn't churn) --
    const handleJobCreated = useCallback((jobId: string) => {
        setActiveJobId(jobId);
        fetchJobs();
        addToast('Analysis job started', 'info');
    }, [fetchJobs, addToast]);

    const handlePlayJob = useCallback((jobId: string) => {
        setActiveJobId(jobId);
        // Additional logic for "playing" if needed
    }, []);

    const handleUpgradeJob = useCallback((job: JobSummary) => {
        setInitialFormState({
            manualPath: job.csv_path || '',
            mode: 'predictive',
            use_cache: true
        });
        addToast("Upgrade mode: Form pre-filled for Predictive Analysis", "info");
    }, [addToast]);

    const handleCancelJob = useCallback(async () => {
        if (activeJobId) {
            try {
                await AnalysisAPI.cancelJob(activeJobId);
                fetchJobs();
                addToast('Job cancelled', 'info');
            } catch (e) {
                addToast('Failed to cancel job', 'error');
            }
        }
    }, [activeJobId, fetchJobs, addToast]);

    const clearInitialFormState = useCallback(() => {
        setInitialFormState(null);
    }, []);

    const value: JobContextType = useMemo(() => ({
        jobs,
        activeJobId,
        isConnected,
        logs: mergedLogs, // Expose the merged logs instead of just socket logs
        events: mergedEvents,
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
    }), [
        jobs, activeJobId, isConnected, mergedLogs, mergedEvents, progress,
        metrics, phases, toasts, initialFormState, fetchJobs, handleJobCreated,
        handlePlayJob, handleUpgradeJob, handleCancelJob, addToast, removeToast,
        clearInitialFormState,
    ]);

    return (
        <JobContext.Provider value={value}>
            {children}
        </JobContext.Provider>
    );
};
