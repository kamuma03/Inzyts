import { type FC } from 'react';
import { NotebookViewer } from '../../NotebookViewer';
import type { JobSummary } from '../../../api';

interface VisualPanelProps {
    job: JobSummary;
}

/** Default Visual tab — shows the rendered notebook (charts + outputs)
 *  for completed jobs. While running, the notebook isn't ready yet so
 *  we render a placeholder pointing the user at the live logs.
 */
export const VisualPanel: FC<VisualPanelProps> = ({ job }) => {
    if (job.status === 'pending' || job.status === 'running') {
        return (
            <div className="h-full flex items-center justify-center text-[12px] text-[var(--text-dim)] p-6 text-center">
                <div>
                    <div className="mb-2">Visual output is generated as the pipeline runs.</div>
                    <div>Switch to <strong className="text-[var(--text-secondary)]">Logs</strong> for live progress.</div>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full">
            <NotebookViewer
                jobId={job.id}
                resultPath={job.result_path ?? null}
                status={job.status}
                mode={job.mode}
            />
        </div>
    );
};
