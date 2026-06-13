import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronRight, Clock, Wifi, WifiOff } from 'lucide-react';
import { useJobContext } from '../context/JobContext';
import { AnalysisAPI, type JobSummary } from '../api';
import { NotebookViewer } from '../components/NotebookViewer';
import { ErrorState } from '../components/state';

/** Full-screen Notebook Workspace route (/workspace/notebook/:jobId).
 *
 *  Rendered OUTSIDE MainLayout so the cell stack gets the whole viewport
 *  (FR-1). A slim breadcrumb strip preserves location and offers the way back
 *  to the job's command center; everything below is the workspace-mode
 *  NotebookViewer (widened column + kernel inspector + chat dock). */
export const NotebookWorkspacePage: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();
    const { jobs, setActiveJobId, isConnected } = useJobContext();

    const [fetchedJob, setFetchedJob] = useState<JobSummary | null>(null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (jobId) setActiveJobId(jobId);
    }, [jobId, setActiveJobId]);

    const jobFromList = jobs.find((j) => j.id === jobId);

    useEffect(() => {
        if (!jobId || jobFromList) {
            setFetchError(null);
            return;
        }
        let cancelled = false;
        setFetchError(null);
        setFetchedJob(null);
        AnalysisAPI.getJobStatus(jobId)
            .then((data) => {
                if (cancelled) return;
                setFetchedJob({ ...data, id: data.id ?? jobId } as JobSummary);
            })
            .catch((err) => {
                if (cancelled) return;
                setFetchError(
                    err?.response?.status === 404
                        ? 'This job could not be found. It may have been deleted.'
                        : 'Could not load this job. Please try again.',
                );
            });
        return () => { cancelled = true; };
    }, [jobId, jobFromList, reloadKey]);

    const job = jobFromList ?? fetchedJob;
    const backToJob = () => navigate(`/jobs/${jobId}`);

    if (fetchError && !job) {
        return (
            <div className="h-screen bg-[var(--surface-0)]">
                <ErrorState
                    title="Job unavailable"
                    body={fetchError}
                    onRetry={() => { setFetchError(null); setReloadKey((k) => k + 1); }}
                />
            </div>
        );
    }

    if (!job) {
        return (
            <div className="h-screen bg-[var(--surface-0)] text-[var(--text-secondary)] p-8 flex items-center gap-3">
                <Clock size={20} className="animate-spin" />
                Loading workspace…
            </div>
        );
    }

    const jobLabel = job.title || job.id;

    return (
        <div className="h-screen flex flex-col bg-[var(--surface-0)] overflow-hidden">
            {/* Breadcrumb strip — preserves location + exit path (FR-1). */}
            <div className="shrink-0 flex items-center gap-1.5 px-4 h-10 border-b border-[var(--rule)] bg-[var(--surface-1)] text-[12px]">
                <img src="/Inzyts_icon.png" alt="" className="w-4 h-4 mr-1" />
                <button
                    onClick={backToJob}
                    className="text-[var(--text-secondary)] hover:text-[var(--accent)] border-none bg-transparent cursor-pointer px-0"
                >
                    {jobLabel}
                </button>
                <ChevronRight size={13} className="text-[var(--text-dim)]" />
                <span className="text-[var(--text-primary)] font-medium">Notebook</span>
                <span className="ml-auto inline-flex items-center gap-1 text-[var(--text-dim)]" title={isConnected ? 'Connected' : 'Disconnected'}>
                    {isConnected ? <Wifi size={13} className="text-[var(--ok)]" /> : <WifiOff size={13} className="text-[var(--bad)]" />}
                </span>
            </div>

            <div className="flex-1 min-h-0">
                <NotebookViewer
                    jobId={jobId!}
                    resultPath={job.result_path ?? null}
                    status={job.status}
                    mode={job.mode}
                    embedded
                    workspace
                    onExitWorkspace={backToJob}
                />
            </div>
        </div>
    );
};
