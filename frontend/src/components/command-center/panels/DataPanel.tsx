import { type FC } from 'react';
import { DataOverview } from '../../DataOverview';

interface DataPanelProps {
    jobId: string;
}

/** Data tab — wraps the existing DataOverview component. Shows the head()
 *  of the resulting dataframe and a column summary. */
export const DataPanel: FC<DataPanelProps> = ({ jobId }) => (
    <div className="h-full min-w-0">
        <DataOverview jobId={jobId} />
    </div>
);
