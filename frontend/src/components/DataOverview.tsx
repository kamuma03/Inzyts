import React from 'react';
import { AnalysisAPI } from '../api';
import { BarChart, Hash } from 'lucide-react';
import {
    BarChart as RechartsBar,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';
import { useFetchData } from '../hooks/useFetchData';
import { ErrorState, EmptyState } from './state';

interface DataOverviewProps {
    jobId: string;
}

interface ColumnInfo {
    name: string;
    type: string;
    missing_count: number;
    missing_pct: number;
    unique_count: number;
    is_numeric: boolean;
}

interface MetricStats {
    count: number;
    mean?: number;
    std?: number;
    min?: number;
    max?: number;
    histogram?: {
        counts: number[];
        bin_edges: number[];
    };
}

interface MetricsResponse {
    row_count: number;
    col_count: number;
    columns: ColumnInfo[];
    numeric_stats: Record<string, MetricStats>;
    preview: Record<string, any>[];
}

export const DataOverview: React.FC<DataOverviewProps> = ({ jobId }) => {
    const { data: metrics, loading, error, refetch } = useFetchData<MetricsResponse>(
        () => AnalysisAPI.getJobMetrics(jobId),
        [jobId],
        { enabled: !!jobId }
    );

    if (loading) {
        return (
            <div className="p-6 flex flex-col gap-6">
                {/* Skeleton stat cards */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="skeleton h-[100px] rounded-lg" />
                    <div className="skeleton h-[100px] rounded-lg" />
                </div>
                {/* Skeleton chart area */}
                <div>
                    <div className="skeleton h-5 w-[200px] mb-4" />
                    <div className="flex gap-6">
                        <div className="skeleton h-[260px] min-w-[380px] rounded-lg" />
                        <div className="skeleton h-[260px] min-w-[380px] rounded-lg" />
                    </div>
                </div>
                {/* Skeleton table */}
                <div>
                    <div className="skeleton h-5 w-[150px] mb-4" />
                    <div className="skeleton h-[200px] rounded-lg" />
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <ErrorState
                title="Couldn't load data preview"
                body="Your job results are still safe — try again or check the status tab."
                onRetry={refetch}
                retrying={loading}
                details={error}
            />
        );
    }

    if (!metrics) {
        return (
            <EmptyState
                icon="database"
                title="No preview yet"
                body="Data preview will appear once the analysis completes."
            />
        );
    }

    return (
        <div className="flex-1 overflow-y-auto min-w-0 max-w-full">
            <div className="p-6 flex flex-col gap-8">

                {/* Summary Header */}
                <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 min-w-0">
                    <div className="p-6 bg-[var(--surface-1)] rounded-lg border border-[var(--rule)] shadow-[0_1px_3px_rgba(0,0,0,0.3)]">
                        <div className="text-[var(--text-secondary)] text-[0.9rem] mb-2 flex items-center gap-2">
                            <Hash size={16} /> Total Rows
                        </div>
                        <div className="text-[2rem] font-semibold text-[var(--text-primary)]">
                            {metrics.row_count.toLocaleString()}
                        </div>
                    </div>
                    <div className="p-6 bg-[var(--surface-1)] rounded-lg border border-[var(--rule)] shadow-[0_1px_3px_rgba(0,0,0,0.3)]">
                        <div className="text-[var(--text-secondary)] text-[0.9rem] mb-2 flex items-center gap-2">
                            <BarChart size={16} /> Columns
                        </div>
                        <div className="text-[2rem] font-semibold text-[var(--text-primary)]">
                            {metrics.col_count.toLocaleString()}
                        </div>
                    </div>
                </div>

                {/* Column Distribution Grid */}
                <div>
                    <h3 className="text-[1.25rem] font-semibold text-[var(--text-primary)] mb-4">Numeric Distributions</h3>
                    <div className="overflow-x-auto pb-4 max-w-full">
                        <div className="flex gap-6 flex-nowrap">
                            {Object.entries(metrics.numeric_stats).map(([colName, stats]) => {
                                const histData = stats.histogram ? stats.histogram.counts.map((count, i) => ({
                                    name: stats.histogram!.bin_edges[i].toFixed(1),
                                    count: count
                                })) : [];

                                return (
                                    <div key={colName} className="bg-[var(--surface-1)] border border-[var(--rule)] rounded-lg p-5 min-w-[380px] shrink-0">
                                        <div className="flex justify-between mb-4">
                                            <div className="font-semibold text-[var(--text-primary)]">{colName}</div>
                                            <div className="text-[0.85rem] text-[var(--text-secondary)]">Mean: {stats.mean?.toFixed(2)}</div>
                                        </div>
                                        <div className="h-[200px] w-full">
                                            {histData.length > 0 ? (
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <RechartsBar data={histData}>
                                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.1)" />
                                                        <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                                                        <YAxis tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                                                        <Tooltip contentStyle={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--rule)', color: 'var(--text-primary)' }} />
                                                        <Bar dataKey="count" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                                                    </RechartsBar>
                                                </ResponsiveContainer>
                                            ) : (
                                                <div className="h-full flex items-center justify-center text-[var(--text-secondary)] text-[0.9rem]">
                                                    No distribution data
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* Data Preview Table */}
                <div>
                    <h3 className="text-[1.25rem] font-semibold text-[var(--text-primary)] mb-4">Data Preview</h3>
                    <div className="overflow-x-auto border border-[var(--rule)] rounded-lg bg-[var(--surface-1)] max-w-full">
                        <table className="w-full border-collapse text-[0.9rem]">
                            <thead className="bg-black/20 border-b border-[var(--rule)]">
                                <tr>
                                    {metrics.columns.map(col => (
                                        <th key={col.name} className="px-4 py-3 text-left font-semibold text-[var(--text-primary)] whitespace-nowrap">
                                            <div className="flex flex-col">
                                                <span>{col.name}</span>
                                                <span className="text-[0.75rem] font-normal text-[var(--text-secondary)]">{col.type}</span>
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.preview.map((row, idx) => (
                                    <tr key={idx} className={idx < metrics.preview.length - 1 ? 'border-b border-white/10' : ''}>
                                        {metrics.columns.map(col => (
                                            <td key={`${idx}-${col.name}`} className="px-4 py-3 text-[var(--text-primary)]">
                                                {row[col.name]?.toString() ?? <span className="text-[var(--text-dim)] italic">null</span>}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    );
};
