
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnalysisForm } from '../components/AnalysisForm';
import { useJobContext } from '../context/JobContext';

export const NewAnalysisPage: React.FC = () => {
    const navigate = useNavigate();
    const { handleJobCreated, initialFormState, setActiveJobId } = useJobContext();

    useEffect(() => {
        // When visiting new analysis, ensure we deselect active job so Context Panel updates
        setActiveJobId(null);
    }, [setActiveJobId]);

    const onJobCreated = (jobId: string) => {
        handleJobCreated(jobId);
        navigate(`/jobs/${jobId}`);
    };

    return (
        <div className="flex-1 overflow-y-hidden z-10">
            <AnalysisForm onJobCreated={onJobCreated} initialValues={initialFormState ?? undefined} />
        </div>
    );
};
