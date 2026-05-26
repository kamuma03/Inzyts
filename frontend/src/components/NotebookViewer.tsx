import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Download, FileText, Shield, AlertTriangle, ChevronDown, ChevronUp, Presentation, Clock, FileCode, BookOpen } from 'lucide-react';
import { LivePanel } from './command-center/panels/live/LivePanel';
import { FollowUpChat } from './FollowUpChat';
import { SkeletonCard, Spinner } from './state';
import { NotebookCellData } from '../types/notebook';

interface NotebookViewerProps {
    jobId: string;
    resultPath: string | null;
    status?: string; // 'running', 'completed', 'failed'
    mode?: string;
    /** When true, the consumer (e.g. CommandCenterView's tab panel) already
     *  provides the outer chrome — drop our border + radius to avoid the
     *  border-inside-a-border-inside-a-border stack. */
    embedded?: boolean;
}

interface ExecutiveSummary {
    key_findings: string[];
    data_quality_highlights: string[];
    recommendations: string[];
    summary_text: string;
    generated_by: string;
}

interface PIIScanResult {
    has_pii: boolean;
    findings: Array<{ pii_type: string; value: string; location: string; severity: string }>;
    scanned_cells: number;
}

type ViewMode = 'report' | 'notebook';
type ExportFormat = 'pdf' | 'html' | 'pptx' | 'markdown' | 'ipynb';

export const NotebookViewer: React.FC<NotebookViewerProps> = ({ jobId, resultPath, status = 'completed', embedded = false }) => {
    const [viewMode, setViewMode] = useState<ViewMode>('report');

    // Notebook tab cells (code + markdown) — fetched on first switch into the
    // Notebook tab and reused thereafter.
    const [cells, setCells] = useState<NotebookCellData[]>([]);
    const [cellsLoading, setCellsLoading] = useState(false);
    const cellsFetchedRef = useRef(false);

    // Report export state
    const [exportLoading, setExportLoading] = useState<ExportFormat | null>(null);
    const [exportMenuOpen, setExportMenuOpen] = useState(false);
    const exportMenuRef = useRef<HTMLDivElement>(null);

    // Executive summary & PII state
    const [executiveSummary, setExecutiveSummary] = useState<ExecutiveSummary | null>(null);
    const [summaryLoading, setSummaryLoading] = useState(false);
    const [summaryExpanded, setSummaryExpanded] = useState(true);
    const [piiResult, setPiiResult] = useState<PIIScanResult | null>(null);

    // Fetch executive summary & PII scan on mount when completed.
    useEffect(() => {
        if (!jobId || status !== 'completed') return;
        let mounted = true;
        setSummaryLoading(true);
        Promise.allSettled([
            AnalysisAPI.getExecutiveSummary(jobId),
            AnalysisAPI.getPIIScan(jobId),
        ]).then(([summaryRes, piiRes]) => {
            if (!mounted) return;
            if (summaryRes.status === 'fulfilled') setExecutiveSummary(summaryRes.value);
            if (piiRes.status === 'fulfilled') setPiiResult(piiRes.value);
        }).finally(() => { if (mounted) setSummaryLoading(false); });
        return () => { mounted = false; };
    }, [jobId, status]);

    // Fetch cells the first time the user opens the Notebook tab.
    useEffect(() => {
        if (viewMode !== 'notebook' || !jobId || cellsFetchedRef.current) return;
        let mounted = true;
        cellsFetchedRef.current = true;
        setCellsLoading(true);
        AnalysisAPI.getNotebookCells(jobId).then((response) => {
            if (mounted && response?.cells) setCells(response.cells);
        }).catch(() => {
            // Non-fatal — the surface will fall back to a single empty cell.
        }).finally(() => { if (mounted) setCellsLoading(false); });
        return () => { mounted = false; };
    }, [viewMode, jobId]);

    // Close export menu on outside click
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
            // .ipynb has its own dedicated endpoint; everything else flows
            // through the unified exportReport pipeline.
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
        } finally {
            setExportLoading(null);
        }
    }, [jobId, resultPath]);

    // View-mode toggle: neutral border when inactive, accent fill when active.
    const modeButtonClass = (mode: ViewMode) =>
        `text-[0.8rem] px-2 py-1 rounded border cursor-pointer flex items-center gap-1 transition-colors ${
            viewMode === mode
                ? 'text-[var(--accent-ink)] bg-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--text-secondary)] bg-transparent border-[var(--rule)] hover:text-[var(--text-primary)] hover:border-[var(--rule-strong)]'
        }`;

    const exportFormats: { key: ExportFormat; label: string; icon: React.ReactNode }[] = useMemo(() => [
        { key: 'pdf' as const, label: 'PDF', icon: <FileText size={14} /> },
        { key: 'html' as const, label: 'HTML', icon: <Download size={14} /> },
        { key: 'pptx' as const, label: 'PowerPoint', icon: <Presentation size={14} /> },
        { key: 'markdown' as const, label: 'Markdown', icon: <FileText size={14} /> },
        ...(resultPath ? [{ key: 'ipynb' as const, label: 'Jupyter (.ipynb)', icon: <FileCode size={14} /> }] : []),
    ], [resultPath]);

    // Show waiting state if job is not completed
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

    return (
        <div className={`mt-0 overflow-hidden h-full flex flex-col min-h-0 ${embedded ? '' : 'border border-[var(--rule)] rounded-lg'}`}>
            {/* Header */}
            <div className="p-4 border-b border-[var(--rule)] bg-[var(--surface-1)] flex justify-between items-center shrink-0">
                <h3 className="m-0 font-semibold text-[var(--text-primary)] flex items-center gap-2">
                    Results Notebook
                    {/* Two surfaces:
                          Report   = executive summary card only
                          Notebook = merged editor + sandbox (Jupyter-style) */}
                    <span className="flex gap-1 ml-2">
                        <button
                            onClick={() => setViewMode('report')}
                            className={modeButtonClass('report')}
                            title="Executive summary of the analysis — quick scan of findings, recommendations, and data quality."
                        >
                            <Shield size={14} />
                            Report
                        </button>
                        <button
                            onClick={() => setViewMode('notebook')}
                            className={modeButtonClass('notebook')}
                            title="Editable notebook — tweak cells with AI, type your own code, and run against the live kernel."
                        >
                            <BookOpen size={14} />
                            Notebook
                        </button>
                    </span>

                    {/* PII Warning Badge */}
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

                {/* Export Controls */}
                <div className="flex items-center gap-2">
                    {/* Export dropdown — also hosts the .ipynb download
                        so download formats sit in one menu. */}
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

            {/* Tab body */}
            <div className="flex-1 min-h-0 overflow-hidden flex flex-col bg-[var(--surface-0)]">
                {viewMode === 'report' ? (
                    <ReportTab
                        summary={executiveSummary}
                        loading={summaryLoading}
                        expanded={summaryExpanded}
                        onToggle={() => setSummaryExpanded((p) => !p)}
                    />
                ) : (
                    <NotebookTab
                        jobId={jobId}
                        cells={cells}
                        cellsLoading={cellsLoading}
                    />
                )}
            </div>
        </div>
    );
};

// ---------------------------------------------------------------------------
// Report tab — executive summary card only.
// ---------------------------------------------------------------------------

interface ReportTabProps {
    summary: ExecutiveSummary | null;
    loading: boolean;
    expanded: boolean;
    onToggle: () => void;
}

const ReportTab: React.FC<ReportTabProps> = ({ summary, loading, expanded, onToggle }) => {
    if (loading && !summary) {
        return (
            <div className="flex-1 flex items-center justify-center p-6">
                <Spinner size="md" caption="Generating summary" />
            </div>
        );
    }
    if (!summary) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 p-6 text-center text-[var(--text-secondary)]">
                <Shield size={32} className="opacity-40" />
                <div className="text-[0.9rem]">No executive summary available for this job.</div>
            </div>
        );
    }
    return (
        <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="border-b border-[var(--rule)]">
                <button
                    onClick={onToggle}
                    className="flex items-center justify-between w-full px-4 py-3 border-none bg-transparent text-[var(--text-primary)] cursor-pointer text-[0.95rem] font-semibold"
                >
                    <span className="flex items-center gap-2">
                        <Shield size={16} className="text-[var(--accent)]" />
                        Executive Summary
                        {summary.generated_by === 'fallback' && (
                            <span className="text-[0.7rem] text-[var(--text-secondary)] font-normal">
                                (extracted)
                            </span>
                        )}
                    </span>
                    {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {expanded && (
                    <div className="px-4 pb-6 text-[0.9rem] text-[var(--text-secondary)]">
                        {summary.summary_text && (
                            <p className="mb-4 leading-normal [text-wrap:pretty]">
                                {summary.summary_text}
                            </p>
                        )}

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                                    Key Findings
                                </h4>
                                <ul className="m-0 pl-4">
                                    {summary.key_findings.map((f, i) => (
                                        <li key={i} className="mb-1 text-[0.85rem]">{f}</li>
                                    ))}
                                </ul>
                            </div>
                            <div>
                                <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                                    Recommendations
                                </h4>
                                <ul className="m-0 pl-4">
                                    {summary.recommendations.map((r, i) => (
                                        <li key={i} className="mb-1 text-[0.85rem]">{r}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>

                        {summary.data_quality_highlights.length > 0 && (
                            <div className="mt-5">
                                <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                                    Data Quality
                                </h4>
                                <ul className="m-0 pl-4">
                                    {summary.data_quality_highlights.map((h, i) => (
                                        <li key={i} className="mb-1 text-[0.85rem]">{h}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

// ---------------------------------------------------------------------------
// Notebook tab — merged editor + sandbox + follow-up chat dock.
// ---------------------------------------------------------------------------

interface NotebookTabProps {
    jobId: string;
    cells: NotebookCellData[];
    cellsLoading: boolean;
}

const NotebookTab: React.FC<NotebookTabProps> = ({ jobId, cells, cellsLoading }) => {
    const seed = useMemo(
        () => cells.map((c) => ({ cell_type: c.cell_type, source: c.source })),
        [cells],
    );

    if (cellsLoading && cells.length === 0) {
        return (
            <div className="flex-1 flex items-center justify-center p-6">
                <Spinner size="md" caption="Loading cells" />
            </div>
        );
    }

    return (
        <div className="flex-1 min-h-0 flex flex-col">
            {/* Cell stack (kernel-backed editing + AI tweak) */}
            <div className="flex-1 min-h-0">
                <LivePanel jobId={jobId} initialNotebookCells={seed} />
            </div>
            {/* Follow-up chat dock at the bottom */}
            <div className="shrink-0 border-t border-[var(--rule)] px-4 py-3">
                <FollowUpChat jobId={jobId} />
            </div>
        </div>
    );
};
