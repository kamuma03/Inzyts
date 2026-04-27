import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TopStrip } from './TopStrip';
import type { JobSummary, RunMetrics } from '../../api';

const baseJob: JobSummary = {
    id: 'abcdef1234567890',
    status: 'running',
    mode: 'forecasting',
    created_at: new Date().toISOString(),
    csv_path: '/data/sales.csv',
    cost_estimate: { total: 0.12, estimated_cost_usd: 0.12 },
    token_usage: { total: 12_000 },
};

const baseMetrics: RunMetrics = {
    job_id: 'abcdef1234567890',
    elapsed_seconds: 90,
    eta_seconds: 30,
    tokens_used: 12_000,
    prompt_tokens: 8_000,
    completion_tokens: 4_000,
    cost_usd: 0.12,
    quality_score: 0.92,
    agents_active: 2,
    agents_total: 22,
    previous_job_id: null,
    previous: null,
};

describe('TopStrip', () => {
    it('renders the filename, mode pill, and short job id', () => {
        render(<TopStrip job={baseJob} metrics={baseMetrics} />);
        expect(screen.getByText('sales.csv')).toBeInTheDocument();
        expect(screen.getByText('forecasting')).toBeInTheDocument();
        expect(screen.getByText(/job_id=abcdef12/)).toBeInTheDocument();
    });

    it('hides delta chips when no previous job exists', () => {
        render(<TopStrip job={baseJob} metrics={baseMetrics} />);
        // No previous → no comparison link rendered
        expect(screen.queryByText(/^vs\./)).not.toBeInTheDocument();
        // No "−" or "+" delta labels
        expect(screen.queryByText(/^[+−]/)).not.toBeInTheDocument();
    });

    it('renders delta chips when previous is provided', () => {
        const m: RunMetrics = {
            ...baseMetrics,
            previous_job_id: 'prev1234abcd5678',
            previous: {
                tokens_used: 15_000,
                cost_usd: 0.20,
                elapsed_seconds: 120,
                quality_score: 0.85,
            },
        };
        render(<TopStrip job={baseJob} metrics={m} />);

        // KPI deltas should be visible — current is lower than previous, so "better".
        // The label format starts with − for negative delta.
        const negativeLabels = screen.getAllByText(/^−/);
        expect(negativeLabels.length).toBeGreaterThanOrEqual(1);

        // Previous job link rendered
        expect(screen.getByText(/^prev1234/)).toBeInTheDocument();
    });

    it('shows Cancel button only while running', () => {
        const { rerender } = render(<TopStrip job={baseJob} metrics={baseMetrics} onCancel={() => {}} />);
        expect(screen.getByLabelText('Cancel job')).toBeInTheDocument();

        const completedJob = { ...baseJob, status: 'completed' };
        rerender(<TopStrip job={completedJob} metrics={baseMetrics} onCancel={() => {}} onExport={() => {}} />);
        expect(screen.queryByLabelText('Cancel job')).not.toBeInTheDocument();
        expect(screen.getByLabelText('Export')).toBeInTheDocument();
    });
});
