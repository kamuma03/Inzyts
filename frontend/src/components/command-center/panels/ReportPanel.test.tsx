import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ReportPanel } from './ReportPanel';
import type { JobSummary } from '../../../api';

vi.mock('../../../api', () => {
    const summary = {
        key_findings: ['Finding A', 'Finding B'],
        data_quality_highlights: ['DQ A'],
        recommendations: ['Reco A'],
        summary_text: 'A short executive summary blurb for the analysis.',
        generated_by: 'llm',
    };
    return {
        AnalysisAPI: {
            getExecutiveSummary: vi.fn().mockResolvedValue(summary),
        },
    };
});

import { AnalysisAPI } from '../../../api';

const completedJob = {
    id: 'job-1',
    status: 'completed',
    progress: 100,
    mode: 'exploratory',
    created_at: '2026-05-26T09:00:00Z',
} as unknown as JobSummary;

const runningJob = {
    id: 'job-2',
    status: 'running',
    progress: 40,
    mode: 'exploratory',
    created_at: '2026-05-26T09:00:00Z',
} as unknown as JobSummary;

describe('ReportPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders the executive summary for a completed job', async () => {
        render(<ReportPanel job={completedJob} />);
        await waitFor(() => {
            expect(screen.getByText('Executive Summary')).toBeInTheDocument();
        });
        expect(screen.getByText('A short executive summary blurb for the analysis.')).toBeInTheDocument();
        expect(screen.getByText('Finding A')).toBeInTheDocument();
        expect(screen.getByText('Finding B')).toBeInTheDocument();
        expect(screen.getByText('Reco A')).toBeInTheDocument();
        expect(screen.getByText('DQ A')).toBeInTheDocument();
        expect(AnalysisAPI.getExecutiveSummary).toHaveBeenCalledWith('job-1');
    });

    it('shows the waiting state while the job is running', () => {
        render(<ReportPanel job={runningJob} />);
        expect(screen.getByText(/Analysis in progress/)).toBeInTheDocument();
        expect(AnalysisAPI.getExecutiveSummary).not.toHaveBeenCalled();
    });
});
