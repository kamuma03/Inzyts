import React, { useEffect, useState, useCallback, useRef } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Terminal, Sparkles, Download, FileText, Shield, AlertTriangle, ChevronDown, ChevronUp, Presentation, Clock, FileCode } from 'lucide-react';
import { LivePanel } from './command-center/panels/live/LivePanel';
import { InteractiveCell } from './InteractiveCell';
import { FollowUpChat } from './FollowUpChat';
import { CellOutput, NotebookCellData } from '../types/notebook';

interface NotebookViewerProps {
    jobId: string;
    resultPath: string | null;
    status?: string; // 'running', 'completed', 'failed'
    mode?: string;
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

type ViewMode = 'static' | 'live' | 'interactive';
type ExportFormat = 'pdf' | 'html' | 'pptx' | 'markdown';

export const NotebookViewer: React.FC<NotebookViewerProps> = ({ jobId, resultPath, status = 'completed' }) => {
    const [htmlContent, setHtmlContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<ViewMode>('static');

    // Interactive mode state
    const [cells, setCells] = useState<NotebookCellData[]>([]);
    const [cellsLoading, setCellsLoading] = useState(false);

    // Report export state
    const [exportLoading, setExportLoading] = useState<ExportFormat | null>(null);
    const [exportMenuOpen, setExportMenuOpen] = useState(false);
    const exportMenuRef = useRef<HTMLDivElement>(null);

    // Executive summary & PII state
    const [executiveSummary, setExecutiveSummary] = useState<ExecutiveSummary | null>(null);
    const [summaryLoading, setSummaryLoading] = useState(false);
    const [summaryExpanded, setSummaryExpanded] = useState(true);
    const [piiResult, setPiiResult] = useState<PIIScanResult | null>(null);

    // Load static HTML
    useEffect(() => {
        let mounted = true;

        const loadNotebook = async () => {
            if (!jobId || !resultPath || status !== 'completed') return;

            try {
                setLoading(true);
                setError(null);
                const response = await AnalysisAPI.getNotebookHtml(jobId);
                if (mounted) {
                    if (typeof response === 'string') {
                        setHtmlContent(response);
                    } else if (response && response.html) {
                        setHtmlContent(response.html);
                    } else {
                        if (import.meta.env.DEV) console.warn("Unexpected notebook response format", response);
                        setError("Failed to load notebook content.");
                    }
                }
            } catch (err) {
                if (mounted) {
                    if (import.meta.env.DEV) console.error("Failed to load notebook", err);
                    setError("Could not load notebook preview.");
                }
            } finally {
                if (mounted) {
                    setLoading(false);
                }
            }
        };

        loadNotebook();

        return () => {
            mounted = false;
        };
    }, [jobId, resultPath, status]);

    // Fetch executive summary & PII scan on mount when completed
    useEffect(() => {
        if (!jobId || status !== 'completed') return;
        let mounted = true;

        const fetchReportData = async () => {
            setSummaryLoading(true);
            try {
                const [summaryRes, piiRes] = await Promise.allSettled([
                    AnalysisAPI.getExecutiveSummary(jobId),
                    AnalysisAPI.getPIIScan(jobId),
                ]);
                if (mounted) {
                    if (summaryRes.status === 'fulfilled') {
                        setExecutiveSummary(summaryRes.value);
                    }
                    if (piiRes.status === 'fulfilled') {
                        setPiiResult(piiRes.value);
                    }
                }
            } finally {
                if (mounted) setSummaryLoading(false);
            }
        };

        fetchReportData();
        return () => { mounted = false; };
    }, [jobId, status]);

    // Load cells when switching to interactive mode
    useEffect(() => {
        if (viewMode !== 'interactive' || !jobId) return;

        let mounted = true;
        const loadCells = async () => {
            setCellsLoading(true);
            try {
                const response = await AnalysisAPI.getNotebookCells(jobId);
                if (mounted && response?.cells) {
                    setCells(response.cells);
                }
            } catch (err) {
                if (mounted) {
                    setError("Failed to load notebook cells.");
                }
            } finally {
                if (mounted) setCellsLoading(false);
            }
        };
        loadCells();
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

    const handleCellUpdate = useCallback((index: number, newCode: string, outputs: CellOutput[]) => {
        setCells(prev => {
            const updated = [...prev];
            updated[index] = { ...updated[index], source: newCode, outputs };
            return updated;
        });
    }, []);

    const handleExport = useCallback(async (format: ExportFormat) => {
        setExportLoading(format);
        setExportMenuOpen(false);
        try {
            const response = await AnalysisAPI.exportReport(jobId, format);
            const blob = new Blob([response.data], { type: response.headers['content-type'] });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const ext = format === 'markdown' ? 'md' : format;
            a.download = `inzyts_report_${jobId}.${ext}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            if (import.meta.env.DEV) console.error(`Export ${format} failed`, err);
        } finally {
            setExportLoading(null);
        }
    }, [jobId]);

    const modeButtonClass = (mode: ViewMode) =>
        `text-[0.8rem] px-2 py-1 rounded border border-[var(--bg-turquoise-surf)] cursor-pointer flex items-center gap-1 ${
            viewMode === mode
                ? 'text-white bg-[var(--bg-turquoise-surf)]'
                : 'text-[var(--bg-turquoise-surf)] bg-transparent'
        }`;

    const exportFormats: { key: ExportFormat; label: string; icon: React.ReactNode }[] = [
        { key: 'pdf', label: 'PDF', icon: <FileText size={14} /> },
        { key: 'html', label: 'HTML', icon: <Download size={14} /> },
        { key: 'pptx', label: 'PowerPoint', icon: <Presentation size={14} /> },
        { key: 'markdown', label: 'Markdown', icon: <FileText size={14} /> },
    ];

    // Show waiting state if job is not completed
    if (status !== 'completed') {
        const isRunning = status === 'running';
        return (
            <div className="mt-0 border border-[var(--border-color)] rounded-lg flex-1 flex flex-col items-center justify-center gap-4 bg-[var(--bg-true-cobalt)] min-h-[300px]">
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
                        {/* Skeleton preview */}
                        <div className="w-4/5 max-w-[500px] flex flex-col gap-2 mt-2">
                            <div className="skeleton h-3.5 w-3/5" />
                            <div className="skeleton h-[60px]" />
                            <div className="skeleton h-3.5 w-2/5" />
                            <div className="skeleton h-20" />
                        </div>
                    </>
                ) : status === 'failed' ? (
                    <>
                        <AlertTriangle size={40} color="#fc8181" className="opacity-60" />
                        <div className="text-red-300 text-[0.95rem]">
                            Analysis failed. Check the Status tab for details.
                        </div>
                    </>
                ) : (
                    <>
                        <FileCode size={40} color="var(--text-secondary)" className="opacity-40" />
                        <div className="text-[var(--text-secondary)] text-[0.9rem]">
                            No notebook available yet.
                        </div>
                    </>
                )}
            </div>
        );
    }

    return (
        <div className="mt-0 border border-[var(--border-color)] rounded-lg overflow-hidden flex-1 flex flex-col min-h-0">
            {/* Header */}
            <div className="p-4 border-b border-[var(--border-color)] bg-[var(--bg-true-cobalt)] flex justify-between items-center shrink-0">
                <h3 className="m-0 font-semibold text-[var(--text-primary)] flex items-center gap-2">
                    Results Notebook
                    {status === 'completed' && (
                        <span className="flex gap-1 ml-2">
                            <button onClick={() => setViewMode('static')} className={modeButtonClass('static')}>
                                Static
                            </button>
                            <button onClick={() => setViewMode('interactive')} className={modeButtonClass('interactive')}>
                                <Sparkles size={14} />
                                Interactive
                            </button>
                            <button onClick={() => setViewMode('live')} className={modeButtonClass('live')}>
                                <Terminal size={14} />
                                Live
                            </button>
                        </span>
                    )}

                    {/* PII Warning Badge */}
                    {piiResult?.has_pii && (
                        <span
                            title={`${piiResult.findings.length} PII item(s) detected`}
                            className="inline-flex items-center gap-[3px] ml-2 px-2 py-0.5 rounded-xl bg-amber-500/15 text-amber-500 text-[0.75rem] font-semibold"
                        >
                            <AlertTriangle size={12} />
                            PII ({piiResult.findings.length})
                        </span>
                    )}
                </h3>

                {/* Export Controls */}
                {status === 'completed' && (
                    <div className="flex items-center gap-2">
                        {/* .ipynb download */}
                        {resultPath && (
                            <button
                                onClick={async () => {
                                    try {
                                        const response = await AnalysisAPI.downloadNotebook(jobId);
                                        const blob = new Blob([response.data], { type: 'application/x-ipynb+json' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = resultPath.split('/').pop() || `notebook_${jobId}.ipynb`;
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                    } catch (err) {
                                        if (import.meta.env.DEV) console.error('Notebook download failed', err);
                                    }
                                }}
                                className="text-[0.8rem] text-[var(--bg-turquoise-surf)] bg-transparent border-none cursor-pointer px-2 py-1"
                            >
                                .ipynb
                            </button>
                        )}

                        {/* Export dropdown */}
                        <div ref={exportMenuRef} className="relative">
                            <button
                                onClick={() => setExportMenuOpen(prev => !prev)}
                                disabled={!!exportLoading}
                                className={`flex items-center gap-1 px-2.5 py-1 rounded-md border border-[var(--bg-turquoise-surf)] bg-[var(--bg-turquoise-surf)] text-white text-[0.8rem] font-medium ${
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
                                <div className="absolute right-0 top-full mt-1 bg-[var(--bg-true-cobalt)] border border-[var(--border-color)] rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.3)] min-w-[160px] z-[100] overflow-hidden">
                                    {exportFormats.map((fmt) => (
                                        <button
                                            key={fmt.key}
                                            onClick={() => handleExport(fmt.key)}
                                            className="flex items-center gap-2 w-full px-3 py-2 border-none bg-transparent text-[var(--text-primary)] text-[0.85rem] cursor-pointer text-left hover:bg-teal-400/10"
                                        >
                                            {fmt.icon}
                                            {fmt.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* Executive Summary Card */}
            {executiveSummary && status === 'completed' && (
                <div className="border-b border-[var(--border-color)] bg-[var(--bg-deep-twilight)] shrink-0">
                    <button
                        onClick={() => setSummaryExpanded(prev => !prev)}
                        className="flex items-center justify-between w-full px-4 py-3 border-none bg-transparent text-[var(--text-primary)] cursor-pointer text-[0.9rem] font-semibold"
                    >
                        <span className="flex items-center gap-2">
                            <Shield size={16} className="text-[var(--bg-turquoise-surf)]" />
                            Executive Summary
                            {executiveSummary.generated_by === 'fallback' && (
                                <span className="text-[0.7rem] text-[var(--text-secondary)] font-normal">
                                    (extracted)
                                </span>
                            )}
                        </span>
                        {summaryExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>

                    {summaryExpanded && (
                        <div className="px-4 pb-4 text-[0.88rem] text-[var(--text-secondary)]">
                            {executiveSummary.summary_text && (
                                <p className="mb-3 leading-normal">
                                    {executiveSummary.summary_text.length > 500
                                        ? executiveSummary.summary_text.slice(0, 497) + '...'
                                        : executiveSummary.summary_text}
                                </p>
                            )}

                            <div className="grid grid-cols-2 gap-4">
                                {/* Key Findings */}
                                <div>
                                    <h4 className="text-[0.8rem] text-[var(--bg-turquoise-surf)] mb-1.5 uppercase tracking-wider">
                                        Key Findings
                                    </h4>
                                    <ul className="m-0 pl-4">
                                        {executiveSummary.key_findings.map((f, i) => (
                                            <li key={i} className="mb-0.5 text-[0.82rem]">{f}</li>
                                        ))}
                                    </ul>
                                </div>

                                {/* Recommendations */}
                                <div>
                                    <h4 className="text-[0.8rem] text-[var(--bg-turquoise-surf)] mb-1.5 uppercase tracking-wider">
                                        Recommendations
                                    </h4>
                                    <ul className="m-0 pl-4">
                                        {executiveSummary.recommendations.map((r, i) => (
                                            <li key={i} className="mb-0.5 text-[0.82rem]">{r}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>

                            {/* Data Quality */}
                            {executiveSummary.data_quality_highlights.length > 0 && (
                                <div className="mt-3">
                                    <h4 className="text-[0.8rem] text-[var(--bg-turquoise-surf)] mb-1.5 uppercase tracking-wider">
                                        Data Quality
                                    </h4>
                                    <ul className="m-0 pl-4">
                                        {executiveSummary.data_quality_highlights.map((h, i) => (
                                            <li key={i} className="mb-0.5 text-[0.82rem]">{h}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Summary loading indicator */}
            {summaryLoading && status === 'completed' && (
                <div className="px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-deep-twilight)] flex items-center gap-2 text-[0.8rem] text-[var(--text-secondary)] shrink-0">
                    <Loader className="animate-spin" size={14} />
                    Generating executive summary...
                </div>
            )}

            {/* Notebook Content */}
            <div className={`relative flex-1 min-h-0 overflow-y-auto ${viewMode === 'interactive' ? 'bg-[var(--bg-deep-twilight)]' : 'bg-white'}`}>
                {loading && viewMode === 'static' && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white/80">
                        <Loader className="animate-spin" size={32} color="var(--bg-turquoise-surf)" />
                    </div>
                )}

                {viewMode === 'interactive' ? (
                    cellsLoading ? (
                        <div className="flex items-center justify-center h-[200px] gap-2 text-[var(--text-secondary)]">
                            <Loader className="animate-spin" size={20} />
                            Loading interactive cells...
                        </div>
                    ) : (
                        <div className="p-4 flex flex-col gap-1">
                            {cells.map((cell, i) => (
                                <InteractiveCell
                                    key={i}
                                    cell={cell}
                                    index={i}
                                    jobId={jobId}
                                    onCellUpdate={handleCellUpdate}
                                />
                            ))}
                            <FollowUpChat jobId={jobId} />
                        </div>
                    )
                ) : viewMode === 'live' ? (
                    <LivePanel
                        jobId={jobId}
                        initialCells={cells
                            .filter((c) => c.cell_type === 'code')
                            .map((c) => c.source)}
                    />
                ) : (
                    error ? (
                        <div className="p-8 text-center text-red-500">
                            {error}
                        </div>
                    ) : htmlContent ? (
                        <iframe
                            srcDoc={htmlContent}
                            className="w-full h-full border-none block"
                            title="Notebook Results"
                            sandbox="allow-same-origin"
                        />
                    ) : (
                        <div className="p-8 text-center text-[var(--text-secondary)] bg-[var(--bg-deep-twilight)] h-full flex items-center justify-center">
                            Loading notebook preview...
                        </div>
                    )
                )}
            </div>
        </div>
    );
};
