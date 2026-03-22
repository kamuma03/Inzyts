import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentTrace } from './AgentTrace'
import { AgentEvent, ProgressUpdate } from '../hooks/useSocket'

const baseProps = {
    status: 'running',
    mode: 'predictive',
    logs: [] as string[],
    events: [] as AgentEvent[],
}

describe('AgentTrace', () => {
    it('renders the Agent Activity Trace heading', () => {
        render(<AgentTrace {...baseProps} />)
        expect(screen.getByText('Agent Activity Trace')).toBeInTheDocument()
    })

    it('renders step labels for non-exploratory modes', () => {
        render(<AgentTrace {...baseProps} mode="predictive" />)

        expect(screen.getByText('Orchestrator')).toBeInTheDocument()
        expect(screen.getByText('Data Profiler')).toBeInTheDocument()
        expect(screen.getByText('Strategy')).toBeInTheDocument()
        expect(screen.getByText('Analysis')).toBeInTheDocument()
        expect(screen.getByText('Finalizing')).toBeInTheDocument()
    })

    it('hides strategy and analysis steps for exploratory mode', () => {
        render(<AgentTrace {...baseProps} mode="exploratory" />)

        expect(screen.getByText('Orchestrator')).toBeInTheDocument()
        expect(screen.getByText('Data Profiler')).toBeInTheDocument()
        expect(screen.getByText('Finalizing')).toBeInTheDocument()
        expect(screen.queryByText('Strategy')).not.toBeInTheDocument()
        expect(screen.queryByText('Analysis')).not.toBeInTheDocument()
    })

    it('shows initializing message when no events or logs', () => {
        render(<AgentTrace {...baseProps} events={[]} logs={[]} />)
        expect(screen.getByText('Initializing...')).toBeInTheDocument()
    })

    it('shows status message from latest event', () => {
        const events: AgentEvent[] = [
            {
                type: 'agent_event',
                event: 'PHASE1_START',
                phase: 'phase1',
                data: { message: 'Starting data profiling...' },
            },
        ]
        render(<AgentTrace {...baseProps} events={events} />)
        expect(screen.getByText('Starting data profiling...')).toBeInTheDocument()
    })

    it('renders progress bar when progress is provided and running', () => {
        const progress: ProgressUpdate = {
            progress: 45,
            message: 'Designing strategy...',
            phase: 'phase2',
            elapsed_seconds: 30,
            eta_seconds: 37,
            phase_timings: { phase1: { elapsed: 20 }, phase2: { elapsed: 10 } },
        }

        render(<AgentTrace {...baseProps} progress={progress} />)

        expect(screen.getByText('45% complete')).toBeInTheDocument()
        expect(screen.getByText(/remaining/i)).toBeInTheDocument()
    })

    it('shows "Calculating..." when progress is very low', () => {
        const progress: ProgressUpdate = {
            progress: 3,
            message: 'Starting...',
            phase: 'phase1',
            elapsed_seconds: 2,
            eta_seconds: null,
            phase_timings: {},
        }

        render(<AgentTrace {...baseProps} progress={progress} />)

        expect(screen.getByText('3% complete')).toBeInTheDocument()
        expect(screen.getByText('Calculating...')).toBeInTheDocument()
    })

    it('does not show progress bar when status is completed', () => {
        const progress: ProgressUpdate = {
            progress: 100,
            message: 'Done',
            phase: 'done',
            elapsed_seconds: 120,
            eta_seconds: null,
            phase_timings: {},
        }

        render(<AgentTrace {...baseProps} status="completed" progress={progress} />)

        // Progress bar only shown when status === 'running'
        expect(screen.queryByText('100% complete')).not.toBeInTheDocument()
    })

    it('does not show progress bar when no progress provided', () => {
        render(<AgentTrace {...baseProps} />)
        expect(screen.queryByText(/% complete/)).not.toBeInTheDocument()
    })

    it('uses progress message as status text when available', () => {
        const progress: ProgressUpdate = {
            progress: 35,
            message: 'Profile locked',
            phase: 'phase1',
            elapsed_seconds: 25,
            eta_seconds: 46,
            phase_timings: {},
        }

        render(<AgentTrace {...baseProps} events={[]} progress={progress} />)
        expect(screen.getByText('Profile locked')).toBeInTheDocument()
    })
})
