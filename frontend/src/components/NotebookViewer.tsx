import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Terminal, Sparkles, Download, FileText, Shield, AlertTriangle, ChevronDown, ChevronUp, Presentation, Clock, FileCode, Sun, Moon } from 'lucide-react';
import { LivePanel } from './command-center/panels/live/LivePanel';
import { InteractiveCell } from './InteractiveCell';
import { FollowUpChat } from './FollowUpChat';
import { CellOutput, NotebookCellData } from '../types/notebook';

type NotebookTheme = 'light' | 'dark';

const NOTEBOOK_THEME_STORAGE_KEY = 'inzyts_notebook_theme';

const readStoredTheme = (): NotebookTheme => {
    if (typeof localStorage === 'undefined') return 'dark';
    const stored = localStorage.getItem(NOTEBOOK_THEME_STORAGE_KEY);
    return stored === 'light' ? 'light' : 'dark';
};

/** Inline CSS overrides applied to the static notebook HTML when the user
 *  selects dark mode. Server-side dark Jinja templating is out of scope for
 *  this UI pass, so the style tag is injected client-side before the iframe
 *  receives the document. */
const DARK_NOTEBOOK_OVERRIDES = `
<style>
  html, body {
    background: #0d1b2a !important;
    color: #e6e7e1 !important;
  }
  .jp-Notebook, .jp-MainAreaWidget, .jp-OutputArea, .jp-OutputArea-output,
  .jp-InputArea-editor, .jp-InputPrompt, .jp-OutputPrompt {
    background: transparent !important;
    color: #e6e7e1 !important;
  }
  .jp-RenderedHTMLCommon, .jp-RenderedHTMLCommon * {
    color: #e6e7e1 !important;
  }
  .jp-Cell, .jp-CodeCell, .jp-MarkdownCell {
    background: rgba(20, 34, 53, 0.6) !important;
    border-color: #2a3b56 !important;
  }
  pre, code, .highlight, .jp-CodeMirrorEditor, .CodeMirror, .cm-editor {
    background: rgba(255, 255, 255, 0.04) !important;
    color: #e6e7e1 !important;
  }
  table {
    background: rgba(20, 34, 53, 0.4) !important;
    color: #e6e7e1 !important;
    border-color: #2a3b56 !important;
  }
  th, td { border-color: #2a3b56 !important; }
  a { color: #4cc9f0 !important; }
  hr { border-color: #2a3b56 !important; }
  blockquote {
    color: #a0aab5 !important;
    border-left-color: #4cc9f0 !important;
  }
  /* Pygments syntax-highlighter token classes emitted by nbconvert.
     The default Pygments style uses dark text on a light background;
     on our dark surface that becomes invisible, so we recolour each
     token group with a monokai-ish palette built from our tokens. */
  .highlight, .highlight pre, pre.highlight {
    background: rgba(255, 255, 255, 0.04) !important;
  }
  .highlight, .highlight .err {
    color: #e6e7e1 !important;
    background: transparent !important;
  }
  /* Names — variables, functions, classes, attributes */
  .highlight .n, .highlight .nv, .highlight .nx, .highlight .nl,
  .highlight .ni, .highlight .py, .highlight .vi, .highlight .vc,
  .highlight .vg, .highlight .vm { color: #e6e7e1 !important; }
  .highlight .nf, .highlight .fm { color: #4cc9f0 !important; }
  .highlight .nc, .highlight .nn, .highlight .ne { color: #fbbf24 !important; }
  .highlight .nb, .highlight .bp { color: #4cc9f0 !important; }
  .highlight .na, .highlight .nd, .highlight .nt { color: #a78bfa !important; }
  /* Keywords */
  .highlight .k, .highlight .kc, .highlight .kd, .highlight .kn,
  .highlight .kp, .highlight .kr, .highlight .kt { color: #f87171 !important; font-weight: 600; }
  /* Strings */
  .highlight .s, .highlight .sa, .highlight .sb, .highlight .sc,
  .highlight .dl, .highlight .sd, .highlight .s2, .highlight .se,
  .highlight .sh, .highlight .si, .highlight .sx, .highlight .sr,
  .highlight .s1, .highlight .ss { color: #34d399 !important; }
  /* Numbers */
  .highlight .m, .highlight .mb, .highlight .mf, .highlight .mh,
  .highlight .mi, .highlight .il, .highlight .mo { color: #fbbf24 !important; }
  /* Comments */
  .highlight .c, .highlight .ch, .highlight .cm, .highlight .c1,
  .highlight .cs, .highlight .cp, .highlight .cpf {
    color: #6c7a89 !important;
    font-style: italic;
  }
  /* Operators / punctuation */
  .highlight .o, .highlight .ow { color: #f87171 !important; }
  .highlight .p, .highlight .pi { color: #a0aab5 !important; }
  /* Diff / prompt-style highlights — keep them readable on dark. */
  .highlight .gd { color: #f87171 !important; background: rgba(248,113,113,0.08) !important; }
  .highlight .gi { color: #34d399 !important; background: rgba(52,211,153,0.08) !important; }
  .highlight .gh, .highlight .gu { color: #4cc9f0 !important; font-weight: 600; }
  .highlight .gp { color: #a78bfa !important; }
  /* nbconvert wraps stderr in a coloured div — keep the warning hue but
     soften the background so it doesn't compete with the surface. */
  .jp-OutputArea-output[data-mime-type="application/vnd.jupyter.stderr"],
  div.output_stderr {
    background: rgba(248, 113, 113, 0.08) !important;
    color: #fca5a5 !important;
  }
</style>`;

const applyNotebookTheme = (html: string, theme: NotebookTheme): string => {
    if (theme === 'light') return html;
    if (html.includes('</head>')) {
        return html.replace('</head>', `${DARK_NOTEBOOK_OVERRIDES}</head>`);
    }
    return `${DARK_NOTEBOOK_OVERRIDES}${html}`;
};

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

    // Notebook theme — persisted across reloads. Default is dark to match the
    // surrounding shell.
    const [notebookTheme, setNotebookTheme] = useState<NotebookTheme>(() => readStoredTheme());
    useEffect(() => {
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem(NOTEBOOK_THEME_STORAGE_KEY, notebookTheme);
        }
    }, [notebookTheme]);

    const themedHtmlContent = useMemo(
        () => (htmlContent ? applyNotebookTheme(htmlContent, notebookTheme) : null),
        [htmlContent, notebookTheme],
    );

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
        `text-[0.8rem] px-2 py-1 rounded border border-[var(--accent)] cursor-pointer flex items-center gap-1 ${
            viewMode === mode
                ? 'text-white bg-[var(--accent)]'
                : 'text-[var(--accent)] bg-transparent'
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
            <div className="mt-0 border border-[var(--rule)] rounded-lg flex-1 flex flex-col items-center justify-center gap-4 bg-[var(--surface-1)] min-h-[300px]">
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
                        {/* Skeleton preview — mirrors the executive-summary card
                            (header line, summary paragraph, then two columns of
                            bullets) so the page doesn't visibly snap on load. */}
                        <div className="w-4/5 max-w-[500px] flex flex-col gap-2 mt-2">
                            <div className="skeleton h-4 w-2/5" />
                            <div className="skeleton h-3 w-full" />
                            <div className="skeleton h-3 w-11/12" />
                            <div className="grid grid-cols-2 gap-3 mt-2">
                                <div className="flex flex-col gap-1.5">
                                    <div className="skeleton h-2.5 w-1/2" />
                                    <div className="skeleton h-2.5 w-full" />
                                    <div className="skeleton h-2.5 w-5/6" />
                                    <div className="skeleton h-2.5 w-3/4" />
                                </div>
                                <div className="flex flex-col gap-1.5">
                                    <div className="skeleton h-2.5 w-1/2" />
                                    <div className="skeleton h-2.5 w-full" />
                                    <div className="skeleton h-2.5 w-2/3" />
                                    <div className="skeleton h-2.5 w-5/6" />
                                </div>
                            </div>
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
        <div className="mt-0 border border-[var(--rule)] rounded-lg overflow-hidden flex-1 flex flex-col min-h-0">
            {/* Header */}
            <div className="p-4 border-b border-[var(--rule)] bg-[var(--surface-1)] flex justify-between items-center shrink-0">
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
                        {viewMode === 'static' && (
                            <button
                                onClick={() => setNotebookTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
                                aria-label={notebookTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                                title={notebookTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                                className="flex items-center gap-1 px-2 py-1 rounded-md border border-[var(--rule)] text-[var(--text-secondary)] bg-transparent text-[12px] cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                            >
                                {notebookTheme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
                                <span className="capitalize">{notebookTheme}</span>
                            </button>
                        )}

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
                                className="text-[0.8rem] text-[var(--accent)] bg-transparent border-none cursor-pointer px-2 py-1"
                            >
                                .ipynb
                            </button>
                        )}

                        {/* Export dropdown */}
                        <div ref={exportMenuRef} className="relative">
                            <button
                                onClick={() => setExportMenuOpen(prev => !prev)}
                                disabled={!!exportLoading}
                                className={`flex items-center gap-1 px-2.5 py-1 rounded-md border border-[var(--accent)] bg-[var(--accent)] text-white text-[0.8rem] font-medium ${
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
                <div className="border-b border-[var(--rule)] bg-[var(--surface-0)] shrink-0">
                    <button
                        onClick={() => setSummaryExpanded(prev => !prev)}
                        className="flex items-center justify-between w-full px-4 py-3 border-none bg-transparent text-[var(--text-primary)] cursor-pointer text-[0.9rem] font-semibold"
                    >
                        <span className="flex items-center gap-2">
                            <Shield size={16} className="text-[var(--accent)]" />
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
                                <p className="mb-3 leading-normal [text-wrap:pretty]">
                                    {executiveSummary.summary_text.length > 500
                                        ? executiveSummary.summary_text.slice(0, 497) + '...'
                                        : executiveSummary.summary_text}
                                </p>
                            )}

                            <div className="grid grid-cols-2 gap-4">
                                {/* Key Findings */}
                                <div>
                                    <h4 className="text-[0.8rem] text-[var(--accent)] mb-1.5 uppercase tracking-wider">
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
                                    <h4 className="text-[0.8rem] text-[var(--accent)] mb-1.5 uppercase tracking-wider">
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
                                    <h4 className="text-[0.8rem] text-[var(--accent)] mb-1.5 uppercase tracking-wider">
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
                <div className="px-4 py-2 border-b border-[var(--rule)] bg-[var(--surface-0)] flex items-center gap-2 text-[0.8rem] text-[var(--text-secondary)] shrink-0">
                    <Loader className="animate-spin" size={14} />
                    Generating executive summary...
                </div>
            )}

            {/* Notebook Content */}
            <div className={`relative flex-1 min-h-0 overflow-y-auto ${
                viewMode === 'interactive' || (viewMode === 'static' && notebookTheme === 'dark')
                    ? 'bg-[var(--surface-0)]'
                    : 'bg-white'
            }`}>
                {loading && viewMode === 'static' && (
                    <div className={`absolute inset-0 flex items-center justify-center ${
                        notebookTheme === 'dark' ? 'bg-[var(--surface-0)]/80' : 'bg-white/80'
                    }`}>
                        <Loader className="animate-spin" size={32} color="var(--accent)" />
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
                    ) : themedHtmlContent ? (
                        <iframe
                            key={notebookTheme}
                            srcDoc={themedHtmlContent}
                            className="w-full h-full border-none block"
                            title="Notebook Results"
                            sandbox="allow-same-origin"
                        />
                    ) : (
                        <div className="p-8 text-center text-[var(--text-secondary)] bg-[var(--surface-0)] h-full flex items-center justify-center">
                            Loading notebook preview...
                        </div>
                    )
                )}
            </div>
        </div>
    );
};
