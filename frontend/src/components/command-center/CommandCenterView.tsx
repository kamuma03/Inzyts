import { useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JobSummary } from '../../api';
import { useJobContext } from '../../context/JobContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { TopStrip } from './TopStrip';
import { PipelineRail } from './PipelineRail';
import { ColumnInspector } from './ColumnInspector';
import { CostBreakdown } from './CostBreakdown';
import { QuestionCard } from './QuestionCard';
import { LogViewer } from '../LogViewer';

interface CommandCenterViewProps {
    job: JobSummary;
}

/** Top-level orchestrator for the new analyst surface. Wires the live socket
 *  data (metrics, phases, logs) into the three-column main grid: PipelineRail
 *  (left, 270px) / preview center (1fr) / ColumnInspector + Cost (right, 320px). */
export const CommandCenterView: FC<CommandCenterViewProps> = ({ job }) => {
    const navigate = useNavigate();
    const { logs, metrics, phases, handleCancelJob } = useJobContext();
    const [selectedColumn, setSelectedColumn] = useState<string | null>(null);

    useKeyboardShortcuts(
        {
            escape: () => setSelectedColumn(null),
        },
        { enabled: true },
    );

    const isCompleted = job.status === 'completed';

    return (
        <div className="flex-1 flex flex-col gap-3 min-h-0 min-w-0">
            <TopStrip
                job={job}
                metrics={metrics}
                onCancel={handleCancelJob}
                onExport={isCompleted ? () => navigate(`/jobs/${job.id}`) : undefined}
            />

            <div
                className="flex-1 grid gap-3 min-h-0"
                style={{ gridTemplateColumns: '270px 1fr 320px' }}
            >
                {/* Left rail */}
                <PipelineRail phases={phases} mode={job.mode} />

                {/* Center stack */}
                <main className="flex flex-col gap-3 min-h-0 min-w-0">
                    <div className="flex-1 min-h-0 border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)] overflow-hidden flex flex-col">
                        <div className="px-3 py-2 border-b border-[var(--border-color)] text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                            Live Logs
                        </div>
                        <div className="flex-1 min-h-0 overflow-hidden">
                            <LogViewer logs={logs} />
                        </div>
                    </div>
                </main>

                {/* Right rail */}
                <aside className="flex flex-col gap-3 min-h-0 min-w-0">
                    <QuestionCard question={job.question ?? null} />
                    <div className="flex-1 min-h-0 min-w-0">
                        <ColumnInspector
                            jobId={job.id}
                            selectedColumn={selectedColumn}
                            onSelect={setSelectedColumn}
                        />
                    </div>
                    <CostBreakdown jobId={job.id} refreshKey={job.status} />
                </aside>
            </div>
        </div>
    );
};
