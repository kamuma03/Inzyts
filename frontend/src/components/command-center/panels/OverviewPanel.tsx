import { type FC } from 'react';
import type { JobSummary, PhaseStatus } from '../../../api';
import { PipelineRail } from '../PipelineRail';
import { ColumnInspector } from '../ColumnInspector';
import { CostBreakdown } from '../CostBreakdown';
import { QuestionCard } from '../QuestionCard';

interface OverviewPanelProps {
    job: JobSummary;
    phases: PhaseStatus[] | null;
    selectedColumn: string | null;
    onSelectColumn: (name: string | null) => void;
}

/** Overview tab — bundles the diagnostic context that previously lived in
 *  the side rails: pipeline progress, the user question, the column
 *  inspector, and the per-phase cost breakdown. Each section gets a sane
 *  amount of room since the whole page width is available. */
export const OverviewPanel: FC<OverviewPanelProps> = ({
    job,
    phases,
    selectedColumn,
    onSelectColumn,
}) => {
    return (
        <div
            className="grid gap-3 p-3 h-full min-h-0 min-w-0"
            style={{ gridTemplateColumns: '300px 1fr 320px' }}
        >
            <div className="min-h-0 min-w-0">
                <PipelineRail phases={phases} mode={job.mode} />
            </div>

            <div className="flex flex-col gap-3 min-h-0 min-w-0">
                <QuestionCard question={job.question ?? null} />
                <div className="flex-1 min-h-0 min-w-0">
                    <ColumnInspector
                        jobId={job.id}
                        selectedColumn={selectedColumn}
                        onSelect={onSelectColumn}
                    />
                </div>
            </div>

            <div className="min-h-0 min-w-0">
                <CostBreakdown jobId={job.id} refreshKey={job.status} />
            </div>
        </div>
    );
};
