import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { JobSummary } from '../api';

interface TokenUsageChartProps {
    jobs: JobSummary[];
}

export const TokenUsageChart: React.FC<TokenUsageChartProps> = ({ jobs }) => {
    // Transform data for chart: Filter completed jobs with usage data, reverse to show chronological
    const data = jobs
        .filter(j => (j.status === 'completed' || j.status === 'failed') && j.token_usage)
        .map(j => {
            const prompt = Number(j.token_usage?.prompt || j.token_usage?.input || 0);
            const completion = Number(j.token_usage?.completion || j.token_usage?.output || 0);
            const total = Number(j.token_usage?.total || 0);
            const hasBreakdown = (prompt + completion) > 0;

            return {
                id: j.id.slice(0, 6),
                prompt: hasBreakdown ? prompt : 0,
                completion: hasBreakdown ? completion : 0,
                // If we have a break down, fallback is 0. If we DON'T have a breakdown, use total.
                fallbackTotal: hasBreakdown ? 0 : total,
                totalToken: total,
                cost: j.cost_estimate?.total || 0
            };
        })
        .reverse();

    if (data.length === 0) {
        return (
            <div className="h-64 w-full bg-white p-4 rounded-lg shadow-sm border border-gray-200 flex items-center justify-center text-gray-400">
                No usage data available yet
            </div>
        );
    }

    return (
        <div className="h-80 w-full bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-semibold text-gray-700">Token Usage History</h3>
                <span className="text-xs text-gray-500">Last {data.length} Jobs</span>
            </div>
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="id" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                        formatter={(value: number, name: string) => {
                            if (value === 0) return [0, name];
                            return [value.toLocaleString(), name === 'fallbackTotal' ? 'Total' : name];
                        }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />
                    <Bar dataKey="totalToken" fill="#805ad5" name="Total Tokens" radius={[4, 4, 4, 4]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};
