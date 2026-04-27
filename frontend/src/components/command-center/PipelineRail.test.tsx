import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PipelineRail } from './PipelineRail';
import type { PhaseStatus } from '../../api';

const phases: PhaseStatus[] = [
    {
        id: 'phase1',
        name: 'Phase 1: Data Understanding',
        status: 'running',
        started_at: 1_000_000,
        finished_at: null,
        retries: 0,
        steps: [
            { id: 'profiling', name: 'Profiling', status: 'running', started_at: 1_000_000, finished_at: null, agents: [
                { name: 'DataProfiler', status: 'running', started_at: 1_000_000, finished_at: null },
            ] },
            { id: 'codegen', name: 'Code Generation', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'validate', name: 'Validation', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
    {
        id: 'extensions',
        name: 'Extensions',
        status: 'queued',
        started_at: null, finished_at: null, retries: 0,
        steps: [
            { id: 'extensions', name: 'Mode-specific enrichment', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
    {
        id: 'phase2',
        name: 'Phase 2: Analysis & Modeling',
        status: 'queued', started_at: null, finished_at: null, retries: 0,
        steps: [
            { id: 'strategy', name: 'Strategy', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'codegen', name: 'Code Generation', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'validate', name: 'Validation', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
];

describe('PipelineRail', () => {
    it('renders the default skeleton when no phases supplied', () => {
        render(<PipelineRail phases={null} mode="forecasting" />);
        expect(screen.getByText('Phase 1: Data Understanding')).toBeInTheDocument();
        expect(screen.getByText('Extensions')).toBeInTheDocument();
        expect(screen.getByText('Phase 2: Analysis & Modeling')).toBeInTheDocument();
    });

    it('renders the running agent name', () => {
        render(<PipelineRail phases={phases} mode="forecasting" />);
        expect(screen.getByText('DataProfiler')).toBeInTheDocument();
    });

    it('marks Strategy and Extensions as skipped in exploratory mode', () => {
        render(<PipelineRail phases={phases} mode="exploratory" />);
        const skippedLabels = screen.getAllByText('skipped');
        // Strategy + Extensions = 2 skipped sub-steps.
        expect(skippedLabels.length).toBe(2);
    });

    it('forecasting mode does not skip extensions or strategy', () => {
        render(<PipelineRail phases={phases} mode="forecasting" />);
        expect(screen.queryAllByText('skipped').length).toBe(0);
    });
});
