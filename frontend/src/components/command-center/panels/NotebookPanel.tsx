import { useMemo, type FC } from 'react';
import type { JobSummary } from '../../../api';
import type { AgentEvent } from '../../../hooks/useSocket';
import { NotebookViewer } from '../../NotebookViewer';

interface NotebookPanelProps {
    job: JobSummary;
    /** Agent-event stream — used to render generated source live while the
     *  job is running (the niche the legacy Code tab served). */
    events: AgentEvent[];
    /** Navigate to the full-screen notebook workspace route. */
    onOpenWorkspace?: () => void;
}

/** Notebook tab — completed jobs show the merged editor (NotebookViewer);
 *  running jobs show a streaming view of the source the codegen agents are
 *  producing, so the user has something useful before the kernel exists. */
export const NotebookPanel: FC<NotebookPanelProps> = ({ job, events, onOpenWorkspace }) => {
    const isCompleted = job.status === 'completed';

    const streamingLines = useMemo(() => {
        if (isCompleted) return [];
        return events
            .filter((e) => /codegen|codegenerator/i.test(String(e.agent ?? '')))
            .slice(-200)
            .map((e) => {
                const data = e.data ?? {};
                const msg = (data as Record<string, unknown>).message;
                return typeof msg === 'string' ? msg : '';
            })
            .filter(Boolean);
    }, [events, isCompleted]);

    if (isCompleted) {
        return (
            <div className="h-full">
                <NotebookViewer
                    jobId={job.id}
                    resultPath={job.result_path ?? null}
                    status={job.status}
                    mode={job.mode}
                    embedded
                    onOpenWorkspace={onOpenWorkspace}
                />
            </div>
        );
    }

    const showLineNumbers = streamingLines.length <= 2000;

    return (
        <div className="h-full flex flex-col min-h-0">
            <div className="shrink-0 px-3 py-1.5 flex items-center text-[11px] text-[var(--text-dim)] border-b border-[var(--rule)]">
                <span className="inline-flex items-center gap-1.5">
                    <span
                        className="inline-block w-1.5 h-1.5 rounded-full animate-pulse"
                        style={{ backgroundColor: 'var(--accent)' }}
                    />
                    Codegen streaming
                </span>
                <span className="ml-auto font-mono">{streamingLines.length} lines</span>
            </div>
            <div className="flex-1 min-h-0 overflow-auto bg-[var(--surface-0)]">
                {streamingLines.length === 0 ? (
                    <div className="p-3 text-[12px] text-[var(--text-dim)]">
                        Waiting for the code generator to start…
                    </div>
                ) : (
                    <pre className={`m-0 px-3 py-3 font-mono text-[12px] text-[var(--text-primary)] whitespace-pre-wrap break-words ${showLineNumbers ? '' : 'no-line-numbers'}`}>
                        {streamingLines.join('\n')}
                    </pre>
                )}
            </div>
        </div>
    );
};
