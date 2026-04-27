import { FC, useState, useEffect, useRef } from 'react';
import { CheckCircle, Circle, Loader2 } from 'lucide-react';
import { AgentEvent, ProgressUpdate } from '../hooks/useSocket';
import { formatDuration } from '../utils/formatters';

interface AgentTraceProps {
    status: string;
    mode: string;
    logs: string[];
    events: AgentEvent[];
    progress?: ProgressUpdate | null;
}

// Live timer component for active steps
const LiveTimer: FC<{ startTime: number }> = ({ startTime }) => {
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);
        return () => clearInterval(interval);
    }, [startTime]);

    return (
        <span className="text-[0.65rem] text-[var(--bg-turquoise-surf)] opacity-80 tabular-nums">
            {formatDuration(elapsed)}
        </span>
    );
};

// Map step IDs to phase keys used by ProgressTracker
const STEP_PHASE_MAP: Record<string, string> = {
    init: 'phase1',
    profile: 'phase1',
    extension: 'phase2',
    strategy: 'phase2',
    codegen: 'phase2',
    finalize: 'phase2',
};

/**
 * @deprecated Use the Command Center surface instead. This component renders
 * the legacy 6-step horizontal trace shown on /jobs/:id when
 * VITE_FEATURE_COMMAND_CENTER is unset/false. Scheduled for removal once the
 * flag is the default — see docs/plans/ui-refresh-plan.md (§7 Rollback).
 */
export const AgentTrace: FC<AgentTraceProps> = ({ status, mode, logs, events, progress }) => {
    // Track when each step became active
    const stepStartTimeRef = useRef<Record<number, number>>({});

    // Define steps based on mode
    const steps = [
        { id: 'init', label: 'Orchestrator' },
        { id: 'profile', label: 'Data Profiler' },
        { id: 'extension', label: 'Extensions', hidden: mode === 'exploratory' || mode === 'predictive' },
        { id: 'strategy', label: 'Strategy', hidden: mode === 'exploratory' },
        { id: 'codegen', label: 'Analysis', hidden: mode === 'exploratory' },
        { id: 'finalize', label: 'Finalizing' }
    ];

    const activeSteps = steps.filter(s => !s.hidden);

    // Determine current step index based on EVENTS if available, fallback to logs
    let currentStepIndex = 0;

    // Helper to find latest event of a type
    const hasEvent = (type: string) => events.some(e => e.event === type);
    const hasAgentEvent = (agent: string, eventStatus: string = 'completed') =>
        events.some(e => e.type === 'agent_event' && e.agent === agent && e.event.toLowerCase().includes(eventStatus));

    if (status === 'completed') {
        currentStepIndex = activeSteps.length;
    } else {
        // Progressive checks based on workflow milestones
        if (hasEvent('PHASE2_COMPLETE')) currentStepIndex = 5; // Finalizing
        else if (hasEvent('VALIDATION_PASSED') && events.filter(e => e.phase === 'phase2').length > 0) currentStepIndex = 5;
        else if (hasAgentEvent('AnalysisCodeGenerator', 'invoked')) currentStepIndex = 4;
        else if (hasAgentEvent('StrategyAgent') || hasAgentEvent('ForecastingStrategyAgent') || hasAgentEvent('ComparativeStrategyAgent')) currentStepIndex = 3;
        else if (hasEvent('PHASE2_START') || hasEvent('PROFILE_LOCK_GRANTED')) currentStepIndex = 2; // Entering Ext/Strategy
        else if (hasEvent('PHASE1_COMPLETE') || hasAgentEvent('ProfileValidatorAgent')) currentStepIndex = 2; // Done profiling
        else if (hasAgentEvent('DataProfiler')) currentStepIndex = 1; // Profiling
        else if (hasEvent('MODE_DETECTED')) currentStepIndex = 0; // Init

        // Fallback to logs if no events yet (e.g. legacy or early start)
        if (events.length === 0 && logs.length > 0) {
            const lastLog = logs[logs.length - 1].toLowerCase();
            if (lastLog.includes('profile') || lastLog.includes('profiler')) currentStepIndex = 1;
            else if (lastLog.includes('extension') || lastLog.includes('forecasting')) currentStepIndex = 2;
            else if (lastLog.includes('strategy')) currentStepIndex = 3;
            else if (lastLog.includes('analysis') || lastLog.includes('code')) currentStepIndex = 4;
            else if (lastLog.includes('assembly') || lastLog.includes('finalize')) currentStepIndex = 5;
        }
    }

    // Record start time when step becomes active
    useEffect(() => {
        if (status === 'running' && !stepStartTimeRef.current[currentStepIndex]) {
            stepStartTimeRef.current[currentStepIndex] = Date.now();
        }
    }, [currentStepIndex, status]);

    // Latest status message from events
    const latestEvent = events.length > 0 ? events[events.length - 1] : null;
    const statusMessage: string = latestEvent ?
        String(latestEvent.data?.message || `${latestEvent.event} - ${latestEvent.agent || ''}`) :
        (logs.length > 0 ? String(logs[logs.length - 1]) : "Initializing...");

    // Get phase elapsed time for a step
    const getStepElapsed = (stepId: string): number | null => {
        if (!progress?.phase_timings) return null;
        const phaseKey = STEP_PHASE_MAP[stepId];
        if (!phaseKey) return null;
        return progress.phase_timings[phaseKey]?.elapsed ?? null;
    };

    const progressPct = progress?.progress ?? 0;
    const etaSeconds = progress?.eta_seconds;

    return (
        <div className="mt-4 p-4 bg-black/20 rounded-lg">
            <h5 className="m-0 mb-4 text-[var(--text-secondary)]">Agent Activity Trace</h5>

            <div className="flex items-center justify-between relative mb-6">
                {/* Connecting Line */}
                <div className="absolute top-3 left-0 right-0 h-0.5 bg-[var(--border-color)] z-0" />
                {/* Completed portion of line */}
                {currentStepIndex > 0 && (
                    <div
                        className="absolute top-3 left-0 h-0.5 bg-[var(--bg-turquoise-surf)] z-0 transition-[width] duration-500 ease-out"
                        style={{ width: `${Math.min(100, (currentStepIndex / (activeSteps.length - 1)) * 100)}%` }}
                    />
                )}

                {activeSteps.map((step, idx) => {
                    const isCompleted = idx < currentStepIndex || status === 'completed';
                    const isActive = idx === currentStepIndex && status === 'running';
                    const completedElapsed = isCompleted ? getStepElapsed(step.id) : null;
                    const activeStartTime = isActive ? stepStartTimeRef.current[idx] : undefined;

                    return (
                        <div key={step.id} className="relative z-[1] flex flex-col items-center gap-1">
                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white transition-all duration-300 ${
                                isCompleted
                                    ? 'bg-[var(--bg-turquoise-surf)] border-2 border-[var(--bg-turquoise-surf)]'
                                    : isActive
                                        ? 'bg-[var(--bg-french-blue)] border-2 border-[var(--bg-french-blue)] shadow-[0_0_12px_rgba(76,201,240,0.4)]'
                                        : 'bg-[var(--bg-deep-twilight)] border-2 border-[var(--border-color)]'
                            }`}>
                                {isCompleted ? <CheckCircle size={14} /> : isActive ? <Loader2 size={14} className="animate-spin" /> : <Circle size={10} />}
                            </div>
                            <span className={`text-[0.75rem] ${isActive || isCompleted ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'} ${isActive ? 'font-semibold' : 'font-normal'}`}>
                                {step.label}
                            </span>
                            {/* Show completed elapsed time */}
                            {completedElapsed !== null && completedElapsed > 0 && (
                                <span className="text-[0.65rem] text-[var(--text-secondary)] opacity-70">
                                    {formatDuration(completedElapsed)}
                                </span>
                            )}
                            {/* Show live timer for active step */}
                            {isActive && activeStartTime && (
                                <LiveTimer startTime={activeStartTime} />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Progress Bar + ETA */}
            {status === 'running' && progress && (
                <div className="mb-4">
                    <div className="w-full h-1 bg-white/10 rounded-sm overflow-hidden">
                        <div
                            className="h-full bg-[var(--bg-turquoise-surf)] rounded-sm transition-[width] duration-500 ease-out"
                            style={{ width: `${Math.max(0, Math.min(100, progressPct))}%` }}
                        />
                    </div>
                    <div className="flex justify-between mt-1.5 text-[0.75rem] text-[var(--text-secondary)]">
                        <span>{progressPct}% complete</span>
                        <span>
                            {progressPct <= 5
                                ? 'Calculating...'
                                : etaSeconds != null
                                    ? `~${formatDuration(etaSeconds)} remaining`
                                    : ''}
                        </span>
                    </div>
                </div>
            )}

            {/* Granular Status Text */}
            <div className="py-3 px-3 bg-white/5 rounded-md text-[0.85rem] text-[var(--text-secondary)] border-l-[3px] border-l-[var(--bg-french-blue)] flex items-center gap-2">
                <Loader2 size={14} className={status === 'running' ? "animate-spin shrink-0" : "shrink-0 opacity-0"} />
                <span className="font-mono text-[0.82rem]">
                    {progress?.message && status === 'running' ? progress.message : statusMessage}
                </span>
            </div>
        </div>
    );
};
