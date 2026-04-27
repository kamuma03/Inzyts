import { useEffect, useMemo, useState, type FC } from 'react';
import { AnalysisAPI, type JobSummary } from '../../../api';
import type { AgentEvent } from '../../../hooks/useSocket';

interface CodePanelProps {
    job: JobSummary;
    events: AgentEvent[];
}

interface CodeCell {
    source: string;
    cell_type?: string;
}

interface NotebookCellsResponse {
    cells: CodeCell[];
    job_id: string;
}

/** Code tab — surfaces the Python the codegen agents are producing.
 *
 *  - Running: best-effort streaming view, rendering the latest agent_event
 *    messages from codegen agents as they arrive. Shows a "● streaming" pill.
 *  - Completed: pulls the final notebook cells via getNotebookCells and
 *    renders them as discrete code blocks. Shows a "● ready" pill.
 *
 *  When the cumulative source crosses 2000 lines we switch off line numbers
 *  to keep the panel responsive (full virtualisation is a V2 follow-up).
 */
export const CodePanel: FC<CodePanelProps> = ({ job, events }) => {
    const [cells, setCells] = useState<CodeCell[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    const isCompleted = job.status === 'completed';

    useEffect(() => {
        if (!isCompleted) return;
        let cancelled = false;
        AnalysisAPI.getNotebookCells(job.id)
            .then((resp: NotebookCellsResponse) => {
                if (cancelled) return;
                setCells(resp.cells.filter((c) => (c.cell_type ?? 'code') === 'code'));
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err?.message ?? 'Failed to load generated code');
            });
        return () => {
            cancelled = true;
        };
    }, [job.id, isCompleted]);

    // Streaming view: take the most recent codegen-related agent events.
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

    const totalSourceLines = useMemo(() => {
        if (isCompleted && cells) {
            return cells.reduce((acc, c) => acc + c.source.split('\n').length, 0);
        }
        return streamingLines.length;
    }, [isCompleted, cells, streamingLines]);

    const showLineNumbers = totalSourceLines <= 2000;

    return (
        <div className="h-full flex flex-col min-h-0">
            <div className="shrink-0 px-3 py-1.5 flex items-center gap-2 text-[11px] text-[var(--text-dim)] border-b border-[var(--border-color)]">
                <span
                    className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        isCompleted ? '' : 'animate-pulse'
                    }`}
                    style={{
                        backgroundColor: isCompleted
                            ? 'var(--status-good)'
                            : 'var(--bg-turquoise-surf)',
                    }}
                />
                <span>{isCompleted ? 'ready' : 'streaming'}</span>
                <span className="ml-auto font-mono">{totalSourceLines} lines</span>
            </div>

            <div className="flex-1 min-h-0 overflow-auto bg-[var(--bg-deep-twilight)]">
                {error && (
                    <div className="p-3 text-[12px] text-[var(--status-bad)]">{error}</div>
                )}

                {isCompleted && cells && cells.length === 0 && !error && (
                    <div className="p-3 text-[12px] text-[var(--text-dim)]">
                        No code cells in the generated notebook.
                    </div>
                )}

                {isCompleted && cells && cells.length > 0 && (
                    <ol className={`m-0 p-0 list-none ${showLineNumbers ? '' : 'no-line-numbers'}`}>
                        {cells.map((cell, idx) => (
                            <li
                                key={idx}
                                className="border-b border-[var(--border-color)] last:border-b-0"
                            >
                                <div className="px-3 py-1 text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                                    Cell {idx + 1}
                                </div>
                                <pre className="m-0 px-3 pb-3 font-mono text-[12px] text-[var(--text-primary)] whitespace-pre-wrap break-words">
                                    {cell.source}
                                </pre>
                            </li>
                        ))}
                    </ol>
                )}

                {!isCompleted && (
                    <div className="p-3">
                        {streamingLines.length === 0 ? (
                            <div className="text-[12px] text-[var(--text-dim)]">
                                Waiting for the code generator to start…
                            </div>
                        ) : (
                            <pre className="m-0 font-mono text-[12px] text-[var(--text-primary)] whitespace-pre-wrap break-words">
                                {streamingLines.join('\n')}
                            </pre>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
