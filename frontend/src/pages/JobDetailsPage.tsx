
import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useJobContext } from '../context/JobContext';
import { CommandCenterView } from '../components/command-center/CommandCenterView';
import { Clock } from 'lucide-react';

export const JobDetailsPage: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const { jobs, setActiveJobId } = useJobContext();

    useEffect(() => {
        if (jobId) {
            setActiveJobId(jobId);
        }
    }, [jobId, setActiveJobId]);

    const selectedJob = jobs.find(j => j.id === jobId);

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
