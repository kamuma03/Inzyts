import { memo, type FC } from 'react';
import type { PhaseStatus, SubStepStatus, AgentSummary } from '../../api';
import { statusVar } from '../../utils/colorScales';
import { formatDuration } from '../../utils/formatters';

interface PhaseBlockProps {
    phase: PhaseStatus;
    /** Sub-step ids that don't apply to the current mode (e.g. exploratory).
     *  These render greyed out so analysts still see the full pipeline shape. */
    inactiveSteps?: Set<string>;
}

const elapsedSeconds = (started: number | null, finished: number | null): number | null => {
    if (started == null) return null;
    const end = finished ?? Date.now() / 1000;
    return Math.max(0, end - started);
};

export const PhaseBlock: FC<PhaseBlockProps> = memo(({ phase, inactiveSteps }) => {
    const phaseElapsed = elapsedSeconds(phase.started_at, phase.finished_at);

    return (
        <div className="border border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)] overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-color)]">
                <span
                    className="inline-block w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: statusVar(phase.status) }}
                    aria-label={`phase ${phase.status}`}
                />
                <span className="text-[12px] font-semibold text-[var(--text-primary)] truncate">
                    {phase.name}
                </span>
                {phaseElapsed != null && (
                    <span className="ml-auto font-mono text-[10px] text-[var(--text-dim)]">
                        {formatDuration(phaseElapsed)}
                    </span>
                )}
            </div>
            <ul className="m-0 p-0 list-none">
                {phase.steps.map((step) => (
                    <SubStepRow
                        key={step.id}
                        step={step}
                        inactive={inactiveSteps?.has(`${phase.id}.${step.id}`) ?? false}
                    />
                ))}
            </ul>
        </div>
    );
});

PhaseBlock.displayName = 'PhaseBlock';

interface SubStepRowProps {
    step: SubStepStatus;
    inactive: boolean;
}

const SubStepRow: FC<SubStepRowProps> = memo(({ step, inactive }) => {
    const stepElapsed = elapsedSeconds(step.started_at, step.finished_at);
    return (
        <li
            className={`px-3 py-2 border-b border-[var(--border-color)] last:border-b-0 ${
                inactive ? 'opacity-40' : ''
            }`}
        >
            <div className="flex items-center gap-2">
                <span
                    className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: statusVar(inactive ? 'queued' : step.status) }}
                />
                <span className="text-[11px] text-[var(--text-secondary)] flex-1">
                    {step.name}
                </span>
                {inactive ? (
                    <span className="text-[9px] uppercase tracking-[1px] text-[var(--text-dim)]">
                        skipped
                    </span>
                ) : (
                    stepElapsed != null && (
                        <span className="font-mono text-[10px] text-[var(--text-dim)]">
                            {formatDuration(stepElapsed)}
                        </span>
                    )
                )}
            </div>
            {step.agents.length > 0 && !inactive && (
                <ul className="mt-1 ml-3 m-0 p-0 list-none">
                    {step.agents.map((agent) => (
                        <AgentRow key={agent.name} agent={agent} />
                    ))}
                </ul>
            )}
        </li>
    );
});

SubStepRow.displayName = 'SubStepRow';

const AgentRow: FC<{ agent: AgentSummary }> = memo(({ agent }) => {
    const isRunning = agent.status === 'running';
    return (
        <li className="flex items-center gap-1.5 py-0.5">
            <span
                className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${isRunning ? 'animate-pulse' : ''}`}
                style={{ backgroundColor: statusVar(agent.status) }}
            />
            <span
                className={`font-mono text-[10.5px] truncate ${
                    isRunning ? 'text-[var(--text-primary)]' : 'text-[var(--text-dim)]'
                }`}
                style={isRunning ? undefined : { color: 'var(--accent-violet)' }}
                title={agent.name}
            >
                {agent.name}
            </span>
        </li>
    );
});

AgentRow.displayName = 'AgentRow';
