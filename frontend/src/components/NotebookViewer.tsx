import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Download, FileText, AlertTriangle, ChevronDown, Presentation, Clock, FileCode } from 'lucide-react';
import { LivePanel } from './command-center/panels/live/LivePanel';
import { FollowUpChat } from './FollowUpChat';
import { SkeletonCard, Spinner } from './state';
import { NotebookCellData } from '../types/notebook';
import { useJobContext } from '../context/JobContext';
import { getErrorMessage } from '../utils/errorMessage';

interface NotebookViewerProps {
    jobId: string;
    resultPath: string | null;
    status?: string; // 'running', 'completed', 'failed'
    mode?: string;
    /** When true, the consumer already provides outer chrome — drop our
     *  border + radius to avoid the border-inside-a-border stack. */
    embedded?: boolean;
}

interface PIIScanResult {
    has_pii: boolean;
    findings: Array<{ pii_type: string; value: string; location: string; severity: string }>;
    scanned_cells: number;
}

type ExportFormat = 'pdf' | 'html' | 'pptx' | 'markdown' | 'ipynb';

/** Notebook surface — the Notebook tab's content. Wraps the merged
 *  editor/sandbox cell stack with an export-menu header and a follow-up
 *  chat dock. Report (executive summary) is a sibling top-level tab now,
 *  not a mode of this component. */
export const NotebookViewer: React.FC<NotebookViewerProps> = ({ jobId, resultPath, status = 'completed', embedded = false }) => {
    const { addToast } = useJobContext();
    const [cells, setCells] = useState<NotebookCellData[]>([]);
    const [cellsLoading, setCellsLoading] = useState(true);

    const [exportLoading, setExportLoading] = useState<ExportFormat | null>(null);
    const [exportMenuOpen, setExportMenuOpen] = useState(false);
    const exportMenuRef = useRef<HTMLDivElement>(null);

    const [piiResult, setPiiResult] = useState<PIIScanResult | null>(null);

    // Fetch cells + PII scan once the job is completed.
    //
    // No ref-based dedup here — under React 18 StrictMode, the effect runs
    // twice in dev (mount → cleanup → mount). A `cellsFetchedRef` would
    // record "fetched" on the first run, then short-circuit the second
    // run; the first run's request resolves after cleanup, so its setState
    // calls are guarded out, and cellsLoading would stay true forever. The
    // GET is idempotent, so we just let the second run fire its own
    // request; only the latest response wins via the `cancelled` flag.
    useEffect(() => {
        if (!jobId || status !== 'completed') return;
        let cancelled = false;
        setCellsLoading(true);
        AnalysisAPI.getNotebookCells(jobId).then((response) => {
            if (cancelled) return;
            if (response?.cells) setCells(response.cells);
        }).catch(() => {
            // Non-fatal — surface falls back to a single empty cell.
        }).finally(() => {
            if (!cancelled) setCellsLoading(false);
        });
        AnalysisAPI.getPIIScan(jobId).then((r) => {
            if (!cancelled) setPiiResult(r);
        }).catch(() => { /* silent */ });
        return () => { cancelled = true; };
    }, [jobId, status]);

    // Close export menu on outside click.
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
                setExportMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    const handleExport = useCallback(async (format: ExportFormat) => {
        setExportLoading(format);
        setExportMenuOpen(false);
        try {
            const isNotebook = format === 'ipynb';
            const response = isNotebook
                ? await AnalysisAPI.downloadNotebook(jobId)
                : await AnalysisAPI.exportReport(jobId, format);
            const contentType = isNotebook
                ? 'application/x-ipynb+json'
                : response.headers['content-type'];
            const blob = new Blob([response.data], { type: contentType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            if (isNotebook) {
                a.download = resultPath?.split('/').pop() || `notebook_${jobId}.ipynb`;
            } else {
                const ext = format === 'markdown' ? 'md' : format;
                a.download = `inzyts_report_${jobId}.${ext}`;
            }
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            if (import.meta.env.DEV) console.error(`Export ${format} failed`, err);
            addToast(
                getErrorMessage(err, `Export to ${format.toUpperCase()} failed`),
                'error',
            );
        } finally {
            setExportLoading(null);
        }
    }, [jobId, resultPath, addToast]);

    const exportFormats: { key: ExportFormat; label: string; icon: React.ReactNode }[] = useMemo(() => [
        { key: 'pdf' as const, label: 'PDF', icon: <FileText size={14} /> },
        { key: 'html' as const, label: 'HTML', icon: <Download size={14} /> },
        { key: 'pptx' as const, label: 'PowerPoint', icon: <Presentation size={14} /> },
        { key: 'markdown' as const, label: 'Markdown', icon: <FileText size={14} /> },
        ...(resultPath ? [{ key: 'ipynb' as const, label: 'Jupyter (.ipynb)', icon: <FileCode size={14} /> }] : []),
    ], [resultPath]);

    // Show waiting state if job is not completed.
    if (status !== 'completed') {
        const isRunning = status === 'running';
        return (
            <div className={`mt-0 h-full flex flex-col items-center justify-center gap-4 bg-[var(--surface-1)] min-h-[300px] ${embedded ? '' : 'border border-[var(--rule)] rounded-lg'}`}>
                {isRunning ? (
                    <>
                        <Clock size={40} color="var(--text-secondary)" className="animate-spin opacity-50" />
                        <div className="text-center">
                            <div className="text-[var(--text-primary)] text-base font-medium mb-1">
                                Analysis in progress
                            </div>
                            <div className="text-[var(--text-secondary)] text-[0.85rem]">
                                The notebook will appear here once the analysis completes.
                            </div>
                        </div>
                        <SkeletonCard variant="notebook" className="w-4/5 max-w-[500px] mt-2" />
                    </>
                ) : status === 'failed' ? (
                    <>
                        <AlertTriangle size={40} className="text-[var(--bad)] opacity-60" />
                        <div className="text-[var(--bad)] text-[0.95rem]">
                            Analysis failed. Check the Status tab for details.
                        </div>
                    </>
                ) : (
                    <div className="flex flex-col items-center gap-3 text-center">
                        <FileCode size={40} className="text-[var(--text-secondary)] opacity-40" />
                        <div>
                            <div className="text-[var(--text-primary)] text-base font-medium mb-1">
                                No notebook yet
                            </div>
                            <div className="text-[var(--text-secondary)] text-[12px] opacity-80">
                                The analysis hasn't produced a notebook for this job.
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    const seed = cells.map((c) => ({ cell_type: c.cell_type, source: c.source }));

    return (
        <div className={`mt-0 overflow-hidden h-full flex flex-col min-h-0 ${embedded ? '' : 'border border-[var(--rule)] rounded-lg'}`}>
            {/* Header — export menu + PII badge */}
            <div className="p-4 border-b border-[var(--rule)] bg-[var(--surface-1)] flex justify-between items-center shrink-0">
                <h3 className="m-0 font-semibold text-[var(--text-primary)] flex items-center gap-2">
                    Notebook
                    {piiResult?.has_pii && (
                        <span
                            title={`${piiResult.findings.length} PII item(s) detected`}
                            className="inline-flex items-center gap-[3px] ml-2 px-2 py-0.5 rounded-md bg-[color-mix(in_srgb,var(--warn)_15%,transparent)] text-[var(--warn)] text-[0.75rem] font-semibold"
                        >
                            <AlertTriangle size={12} />
                            PII ({piiResult.findings.length})
                        </span>
                    )}
                </h3>

                <div className="flex items-center gap-2">
                    <div ref={exportMenuRef} className="relative">
                        <button
                            onClick={() => setExportMenuOpen(prev => !prev)}
                            disabled={!!exportLoading}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-md bg-[var(--accent)] text-[var(--accent-ink)] text-[0.8rem] font-semibold hover:brightness-110 transition ${
                                exportLoading ? 'cursor-wait' : 'cursor-pointer'
                            }`}
                        >
                            {exportLoading ? (
                                <Loader className="animate-spin" size={14} />
                            ) : (
                                <Download size={14} />
                            )}
                            {exportLoading ? `Exporting ${exportLoading.toUpperCase()}...` : 'Export'}
                            <ChevronDown size={12} />
                        </button>
                        {exportMenuOpen && (
                            <div className="absolute right-0 top-full mt-1 bg-[var(--surface-1)] border border-[var(--rule)] rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.3)] min-w-[160px] z-[100] overflow-hidden">
                                {exportFormats.map((fmt) => (
                                    <button
                                        key={fmt.key}
                                        onClick={() => handleExport(fmt.key)}
                                        className="flex items-center gap-2 w-full px-3 py-2 border-none bg-transparent text-[var(--text-primary)] text-[0.85rem] cursor-pointer text-left hover:bg-[var(--accent-soft)]"
                                    >
                                        {fmt.icon}
                                        {fmt.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Body */}
            <div className="flex-1 min-h-0 flex flex-col bg-[var(--surface-0)]">
                {cellsLoading && cells.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center p-6">
                        <Spinner size="md" caption="Loading cells" />
                    </div>
                ) : (
                    <>
                        <div className="flex-1 min-h-0">
                            <LivePanel jobId={jobId} initialNotebookCells={seed} />
                        </div>
                        <div className="shrink-0 border-t border-[var(--rule)] px-4 py-3">
                            <FollowUpChat jobId={jobId} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
