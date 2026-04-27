import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { LivePanel } from './LivePanel';
import type { UseSocketHandlers } from '../../../../hooks/useSocket';
import type {
    CellCompleteEvent,
    CellOutputEvent,
    CellStatusEvent,
} from './types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../../../api', async () => {
    return {
        AnalysisAPI: {
            executeLiveCell: vi.fn().mockResolvedValue({
                execution_id: 'exec-1',
                success: true,
                error_name: null,
                error_value: null,
                duration_ms: 12,
                killed_reason: null,
                execution_count: 1,
            }),
            restartLiveKernel: vi.fn().mockResolvedValue({ job_id: 'j1', status: 'restarted' }),
            interruptLiveKernel: vi.fn().mockResolvedValue({ job_id: 'j1', status: 'interrupted' }),
        },
    };
});

// Capture the handlers passed to useSocket so the test can drive WS events.
let capturedHandlers: UseSocketHandlers | undefined;
vi.mock('../../../../hooks/useSocket', () => ({
    useSocket: (_jobId: string | null, handlers?: UseSocketHandlers) => {
        capturedHandlers = handlers;
        return { logs: [], events: [], progress: null, metrics: null, phases: null, isConnected: false };
    },
}));

import { AnalysisAPI } from '../../../../api';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LivePanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        capturedHandlers = undefined;
    });

    it('renders the supplied initial cells in source textareas', () => {
        render(
            <LivePanel
                jobId="job-1"
                initialCells={['import pandas as pd', 'df.head()']}
            />,
        );
        const textareas = screen.getAllByRole('textbox');
        expect(textareas).toHaveLength(2);
        expect((textareas[0] as HTMLTextAreaElement).value).toBe('import pandas as pd');
        expect((textareas[1] as HTMLTextAreaElement).value).toBe('df.head()');
    });

    it('Run button calls executeLiveCell with the cell source', async () => {
        render(<LivePanel jobId="job-1" initialCells={['print(1+1)']} />);
        const runBtn = screen.getByLabelText('Run cell');
        await act(async () => {
            fireEvent.click(runBtn);
        });
        expect(AnalysisAPI.executeLiveCell).toHaveBeenCalledTimes(1);
        const [jobId, code, executionId] = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0];
        expect(jobId).toBe('job-1');
        expect(code).toBe('print(1+1)');
        expect(executionId).toMatch(/^exec-/);
    });

    it('renders streamed stdout output from cell_output events', async () => {
        render(<LivePanel jobId="job-1" initialCells={['print("hi")']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });

        // Find the execution_id the panel registered.
        const callArgs = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0];
        const execId = callArgs[2] as string;

        const statusEvent: CellStatusEvent = {
            execution_id: execId, job_id: 'job-1', execution_state: 'busy',
        };
        const outputEvent: CellOutputEvent = {
            execution_id: execId,
            job_id: 'job-1',
            output: { output_type: 'stream', name: 'stdout', text: 'hi\n' },
        };
        const completeEvent: CellCompleteEvent = {
            execution_id: execId,
            job_id: 'job-1',
            success: true,
            error_name: null,
            error_value: null,
            execution_count: 1,
            duration_ms: 12,
            killed_reason: null,
        };

        await act(async () => {
            capturedHandlers?.onCellStatus?.(statusEvent);
            capturedHandlers?.onCellOutput?.(outputEvent);
            capturedHandlers?.onCellComplete?.(completeEvent);
        });

        await waitFor(() => {
            expect(screen.getByText('hi')).toBeInTheDocument();
        });
        // Execution count badge updated:
        expect(screen.getByText(/^\[1\]$/)).toBeInTheDocument();
    });

    it('renders error traceback when complete event reports failure', async () => {
        render(<LivePanel jobId="job-1" initialCells={['1/0']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });
        const execId = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0][2] as string;

        await act(async () => {
            capturedHandlers?.onCellOutput?.({
                execution_id: execId,
                job_id: 'job-1',
                output: {
                    output_type: 'error',
                    ename: 'ZeroDivisionError',
                    evalue: 'division by zero',
                    traceback: ['Traceback (most recent call last):', '  File line', 'ZeroDivisionError'],
                },
            });
            capturedHandlers?.onCellComplete?.({
                execution_id: execId,
                job_id: 'job-1',
                success: false,
                error_name: 'ZeroDivisionError',
                error_value: 'division by zero',
                execution_count: null,
                duration_ms: 5,
                killed_reason: null,
            });
        });

        await waitFor(() => {
            expect(screen.getByText(/ZeroDivisionError: division by zero/)).toBeInTheDocument();
        });
    });

    it('Restart kernel button clears outputs and resets execution counts', async () => {
        render(<LivePanel jobId="job-1" initialCells={['x = 1']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });
        const execId = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0][2] as string;
        await act(async () => {
            capturedHandlers?.onCellOutput?.({
                execution_id: execId,
                job_id: 'job-1',
                output: { output_type: 'stream', name: 'stdout', text: 'first run output\n' },
            });
            capturedHandlers?.onCellComplete?.({
                execution_id: execId,
                job_id: 'job-1',
                success: true,
                error_name: null,
                error_value: null,
                execution_count: 1,
                duration_ms: 12,
                killed_reason: null,
            });
        });
        expect(screen.getByText('first run output')).toBeInTheDocument();

        // Restart — outputs disappear, execution count becomes [ ].
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Restart kernel'));
        });
        await waitFor(() => {
            expect(screen.queryByText('first run output')).not.toBeInTheDocument();
        });
        expect(AnalysisAPI.restartLiveKernel).toHaveBeenCalledWith('job-1');
    });

    it('Stop button calls interruptLiveKernel while cell is busy', async () => {
        render(<LivePanel jobId="job-1" initialCells={['import time; time.sleep(60)']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });
        const execId = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0][2] as string;

        // Flip the cell into busy state via WS event.
        await act(async () => {
            capturedHandlers?.onCellStatus?.({
                execution_id: execId, job_id: 'job-1', execution_state: 'busy',
            });
        });
        // Now the Run button is replaced by Stop.
        const stopBtn = await screen.findByLabelText('Stop cell');
        await act(async () => {
            fireEvent.click(stopBtn);
        });
        expect(AnalysisAPI.interruptLiveKernel).toHaveBeenCalledWith('job-1');
    });
});
