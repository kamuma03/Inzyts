import { useMemo, type FC } from 'react';
import type { PhaseStatus } from '../../api';
import { PhaseBlock } from './PhaseBlock';
import { Workflow } from 'lucide-react';

interface PipelineRailProps {
    phases: PhaseStatus[] | null;
    /** Current pipeline mode — controls which sub-steps show as greyed/skipped. */
    mode: string | null | undefined;
}

/** Default skeleton shown before the first phase_update arrives.
 *  Matches the structure produced by PhaseStateTracker on the backend. */
const DEFAULT_SKELETON: PhaseStatus[] = [
    {
        id: 'phase1',
        name: 'Phase 1: Data Understanding',
        status: 'queued',
        started_at: null,
        finished_at: null,
        retries: 0,
        steps: [
            { id: 'profiling', name: 'Profiling', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'codegen', name: 'Code Generation', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'validate', name: 'Validation', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
    {
        id: 'extensions',
        name: 'Extensions',
        status: 'queued',
        started_at: null,
        finished_at: null,
        retries: 0,
        steps: [
            { id: 'extensions', name: 'Mode-specific enrichment', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
    {
        id: 'phase2',
        name: 'Phase 2: Analysis & Modeling',
        status: 'queued',
        started_at: null,
        finished_at: null,
        retries: 0,
        steps: [
            { id: 'strategy', name: 'Strategy', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'codegen', name: 'Code Generation', status: 'queued', started_at: null, finished_at: null, agents: [] },
            { id: 'validate', name: 'Validation', status: 'queued', started_at: null, finished_at: null, agents: [] },
        ],
    },
];

/** Sub-steps that don't apply for a given mode — rendered greyed in the rail
 *  so analysts can still see the full pipeline shape. Matches the backend's
 *  agent → (phase, step) attribution map. */
const INACTIVE_BY_MODE: Record<string, string[]> = {
    exploratory: ['extensions.extensions', 'phase2.strategy'],
    predictive: ['extensions.extensions'],
    segmentation: ['extensions.extensions'],
    dimensionality_reduction: ['extensions.extensions'],
    forecasting: [],
    comparative: [],
    diagnostic: [],
};

export const PipelineRail: FC<PipelineRailProps> = ({ phases, mode }) => {
    const data = phases && phases.length > 0 ? phases : DEFAULT_SKELETON;

    const inactive = useMemo(() => {
        const list = (mode && INACTIVE_BY_MODE[mode]) || [];
        return new Set(list);
    }, [mode]);

    return (
        <aside className="flex flex-col gap-3 min-h-0">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                <Workflow size={12} />
                <span>Pipeline</span>
            </div>
            <div className="flex flex-col gap-2 overflow-y-auto min-h-0">
                {data.map((phase) => (
                    <PhaseBlock key={phase.id} phase={phase} inactiveSteps={inactive} />
                ))}
            </div>
        </aside>
    );
};
