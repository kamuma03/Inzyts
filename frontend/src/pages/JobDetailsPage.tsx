
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useJobContext } from '../context/JobContext';
import { AnalysisAPI, type JobSummary } from '../api';
import { CommandCenterView } from '../components/command-center/CommandCenterView';
import { ErrorState } from '../components/state';
import { Clock } from 'lucide-react';

export const JobDetailsPage: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const { jobs, setActiveJobId } = useJobContext();

    // When the job isn't in the context list (which is fetched with a small
    // limit), a deep link to an older job would otherwise spin forever. We
    // fall back to fetching the single job by id and surface an ErrorState on
    // failure instead of an infinite spinner.
    const [fetchedJob, setFetchedJob] = useState<JobSummary | null>(null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (jobId) {
            setActiveJobId(jobId);
        }
    }, [jobId, setActiveJobId]);

    const jobFromList = jobs.find(j => j.id === jobId);

    useEffect(() => {
        // Only fetch when the job is absent from the context list. Once it
        // appears there (e.g. a poll catches up), prefer the live list entry.
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
                // getJobStatus returns the full job record; coerce to the
                // JobSummary shape CommandCenterView consumes.
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

    const selectedJob = jobFromList ?? fetchedJob;

    if (fetchError && !selectedJob) {
        return (
            <ErrorState
                title="Job unavailable"
                body={fetchError}
                onRetry={() => { setFetchError(null); setReloadKey(k => k + 1); }}
            />
        );
    }

    if (!selectedJob) {
        return (
            <div className="text-[var(--text-secondary)] p-8 flex items-center gap-3">
                <Clock size={20} className="animate-spin" />
                Loading job details...
            </div>
        );
    }

    return <CommandCenterView job={selectedJob} />;
};
