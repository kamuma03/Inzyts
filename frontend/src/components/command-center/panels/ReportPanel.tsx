import { useEffect, useState, type FC } from 'react';
import { AnalysisAPI, type JobSummary } from '../../../api';
import { Shield, AlertTriangle, Clock } from 'lucide-react';
import { Spinner } from '../../state';

interface ExecutiveSummary {
    key_findings: string[];
    data_quality_highlights: string[];
    recommendations: string[];
    summary_text: string;
    generated_by: string;
}

interface ReportPanelProps {
    job: JobSummary;
}

/** Report tab — renders the executive summary card for a completed job.
 *
 *  Sibling of the Notebook tab; intentionally narrow scope (just the
 *  summary). Detailed analysis lives in the Notebook tab. */
export const ReportPanel: FC<ReportPanelProps> = ({ job }) => {
    const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (job.status !== 'completed') return;
        let mounted = true;
        setLoading(true);
        setError(null);
        AnalysisAPI.getExecutiveSummary(job.id).then((res) => {
            if (mounted) setSummary(res);
        }).catch((e) => {
            if (mounted) setError(e?.message ?? 'Failed to load executive summary');
        }).finally(() => { if (mounted) setLoading(false); });
        return () => { mounted = false; };
    }, [job.id, job.status]);

    if (job.status === 'pending' || job.status === 'running') {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 p-6 text-center text-[var(--text-secondary)]">
                <Clock size={32} className="animate-spin opacity-50" />
                <div className="text-[var(--text-primary)] text-base font-medium">
                    Analysis in progress
                </div>
                <div className="text-[0.85rem]">
                    The executive summary will appear here once the analysis completes.
                </div>
            </div>
        );
    }

    if (job.status === 'failed') {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 p-6 text-center">
                <AlertTriangle size={32} className="text-[var(--bad)] opacity-60" />
                <div className="text-[var(--bad)] text-[0.95rem]">
                    Analysis failed — no executive summary available.
                </div>
            </div>
        );
    }

    if (loading && !summary) {
        return (
            <div className="h-full flex items-center justify-center p-6">
                <Spinner size="md" caption="Generating summary" />
            </div>
        );
    }

    if (error || !summary) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-2 p-6 text-center text-[var(--text-secondary)]">
                <Shield size={32} className="opacity-40" />
                <div className="text-[0.9rem]">
                    {error ?? 'No executive summary available for this job.'}
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto">
            <div className="p-5">
                <div className="flex items-center gap-2 mb-4">
                    <Shield size={18} className="text-[var(--accent)]" />
                    <h2 className="m-0 text-[1rem] font-semibold text-[var(--text-primary)]">
                        Executive Summary
                    </h2>
                    {summary.generated_by === 'fallback' && (
                        <span className="text-[0.7rem] text-[var(--text-secondary)] font-normal">
                            (extracted)
                        </span>
                    )}
                </div>

                {summary.summary_text && (
                    <p className="mb-5 leading-normal text-[0.95rem] text-[var(--text-secondary)] [text-wrap:pretty]">
                        {summary.summary_text}
                    </p>
                )}

                <div className="grid grid-cols-2 gap-6">
                    <div>
                        <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                            Key Findings
                        </h4>
                        <ul className="m-0 pl-4 text-[var(--text-secondary)]">
                            {summary.key_findings.map((f, i) => (
                                <li key={i} className="mb-1 text-[0.88rem] leading-normal">{f}</li>
                            ))}
                        </ul>
                    </div>
                    <div>
                        <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                            Recommendations
                        </h4>
                        <ul className="m-0 pl-4 text-[var(--text-secondary)]">
                            {summary.recommendations.map((r, i) => (
                                <li key={i} className="mb-1 text-[0.88rem] leading-normal">{r}</li>
                            ))}
                        </ul>
                    </div>
                </div>

                {summary.data_quality_highlights.length > 0 && (
                    <div className="mt-5">
                        <h4 className="text-[11px] text-[var(--text-dim)] mb-1.5 uppercase tracking-[0.04em] font-semibold">
                            Data Quality
                        </h4>
                        <ul className="m-0 pl-4 text-[var(--text-secondary)]">
                            {summary.data_quality_highlights.map((h, i) => (
                                <li key={i} className="mb-1 text-[0.88rem] leading-normal">{h}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};
