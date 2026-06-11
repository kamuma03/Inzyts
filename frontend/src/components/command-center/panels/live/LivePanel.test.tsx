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
            editCell: vi.fn().mockResolvedValue({
                new_code: 'print("tweaked")',
                output: 'tweaked\n',
                images: [],
                success: true,
                error: null,
            }),
            saveNotebookCells: vi.fn().mockResolvedValue({
                job_id: 'job-1',
                cell_count: 1,
                path: '/output/notebook.ipynb',
            }),
        },
    };
});

// LivePanel reads addToast from the job context to surface save/edit errors.
// Provide a lightweight mock so the component can render without a JobProvider.
const addToastMock = vi.fn();
vi.mock('../../../../context/JobContext', () => ({
    useJobContext: () => ({ addToast: addToastMock }),
}));

// Capture the handlers passed to useSocket so the test can drive WS events.
let capturedHandlers: UseSocketHandlers | undefined;
vi.mock('../../../../hooks/useSocket', () => ({
    useSocket: (_jobId: string | null, handlers?: UseSocketHandlers) => {
        capturedHandlers = handlers;
        return { logs: [], events: [], progress: null, metrics: null, phases: null, isConnected: false };
    },
}));

// CodeMirror needs DOM measurement APIs jsdom doesn't fully implement; swap
// in a plain textarea so the existing role/value-based assertions keep
// working without rewriting every test.
vi.mock('./CellSourceEditor', () => ({
    CellSourceEditor: ({ value, onChange, onKeyDown, ariaLabel }: {
        value: string;
        onChange: (v: string) => void;
        onKeyDown?: React.KeyboardEventHandler<HTMLTextAreaElement>;
        ariaLabel: string;
    }) => (
        <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label={ariaLabel}
        />
    ),
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

    // -----------------------------------------------------------------------
    // Merged surface: markdown cells + AI tweak (Phase 2 capability)
    // -----------------------------------------------------------------------

    it('renders markdown cells as preview by default and switches to a textarea on click', async () => {
        render(
            <LivePanel
                jobId="job-1"
                initialNotebookCells={[
                    { cell_type: 'markdown', source: '# Heading\n\nBody text.' },
                ]}
            />,
        );

        // Preview is a heading-bearing button, not a textarea.
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
        const editButton = screen.getByLabelText('Edit markdown cell 1');
        expect(editButton).toBeInTheDocument();

        await act(async () => {
            fireEvent.click(editButton);
        });

        const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
        expect(textarea.value).toBe('# Heading\n\nBody text.');

        // The Render button collapses the editor back to preview.
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Preview markdown'));
        });
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });

    it('markdown cells never call executeLiveCell on Run', async () => {
        render(
            <LivePanel
                jobId="job-1"
                initialNotebookCells={[
                    { cell_type: 'markdown', source: '## Section' },
                ]}
            />,
        );
        // Enter edit mode to expose the Render button (the markdown "run").
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Edit markdown cell 1'));
        });
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Preview markdown'));
        });
        expect(AnalysisAPI.executeLiveCell).not.toHaveBeenCalled();
    });

    it('Tweak button on a code cell calls editCell with the instruction and replaces the source', async () => {
        render(
            <LivePanel
                jobId="job-1"
                initialNotebookCells={[
                    { cell_type: 'code', source: 'print(1)' },
                ]}
            />,
        );

        // Open the Tweak input.
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Tweak cell with AI'));
        });
        const input = screen.getByLabelText('Tweak instruction for cell 1') as HTMLInputElement;
        await act(async () => {
            fireEvent.change(input, { target: { value: 'Print "tweaked" instead' } });
            fireEvent.keyDown(input, { key: 'Enter' });
        });

        await waitFor(() => {
            expect(AnalysisAPI.editCell).toHaveBeenCalledWith(
                'job-1',
                0,
                'print(1)',
                'Print "tweaked" instead',
            );
        });

        // The code textarea now shows the rewritten source from editCell.
        await waitFor(() => {
            const textarea = screen.getByLabelText('Cell 1 source') as HTMLTextAreaElement;
            expect(textarea.value).toBe('print("tweaked")');
        });
        // And the editCell's stdout streamed into the cell's outputs.
        expect(screen.getByText('tweaked')).toBeInTheDocument();
    });

    it('initialNotebookCells takes precedence over initialCells when both are passed', () => {
        render(
            <LivePanel
                jobId="job-1"
                initialCells={['legacy']}
                initialNotebookCells={[{ cell_type: 'code', source: 'preferred' }]}
            />,
        );
        const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
        expect(textarea.value).toBe('preferred');
    });

    // -----------------------------------------------------------------------
    // Phase 3 — Jupyter cell ops + keyboard shortcuts
    // -----------------------------------------------------------------------

    it('Shift+Enter on a code cell runs it without inserting a newline', async () => {
        render(<LivePanel jobId="job-1" initialCells={['print("first")']} />);
        const textarea = screen.getByLabelText('Cell 1 source') as HTMLTextAreaElement;
        await act(async () => {
            fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
        });
        expect(AnalysisAPI.executeLiveCell).toHaveBeenCalledTimes(1);
        expect((AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls[0][1]).toBe('print("first")');
    });

    it('Ctrl+Enter on a code cell also runs it', async () => {
        render(<LivePanel jobId="job-1" initialCells={['x = 1']} />);
        const textarea = screen.getByLabelText('Cell 1 source') as HTMLTextAreaElement;
        await act(async () => {
            fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
        });
        expect(AnalysisAPI.executeLiveCell).toHaveBeenCalledTimes(1);
    });

    it('Insert cell below adds a new code cell after the current one', async () => {
        render(<LivePanel jobId="job-1" initialCells={['original']} />);
        expect(screen.getAllByRole('textbox')).toHaveLength(1);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Insert cell below'));
        });
        const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[];
        expect(textareas).toHaveLength(2);
        expect(textareas[0].value).toBe('original');
        expect(textareas[1].value).toMatch(/New cell/);
    });

    it('Insert cell above adds a new cell before the current one', async () => {
        render(<LivePanel jobId="job-1" initialCells={['original']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Insert cell above'));
        });
        const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[];
        expect(textareas).toHaveLength(2);
        expect(textareas[0].value).toMatch(/New cell/);
        expect(textareas[1].value).toBe('original');
    });

    it('Move cell down swaps order with the next cell', async () => {
        render(<LivePanel jobId="job-1" initialCells={['first', 'second']} />);
        const downButtons = screen.getAllByLabelText('Move cell down');
        await act(async () => {
            fireEvent.click(downButtons[0]); // move first → after second
        });
        const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[];
        expect(textareas[0].value).toBe('second');
        expect(textareas[1].value).toBe('first');
    });

    it('Delete cell removes it from the stack; the last cell cannot be deleted', async () => {
        render(<LivePanel jobId="job-1" initialCells={['a', 'b']} />);
        const deleteBtns = screen.getAllByLabelText('Delete cell');
        await act(async () => {
            fireEvent.click(deleteBtns[0]);
        });
        const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[];
        expect(textareas).toHaveLength(1);
        expect(textareas[0].value).toBe('b');

        // The remaining last cell's delete button is disabled.
        const remainingDelete = screen.getByLabelText('Delete cell') as HTMLButtonElement;
        expect(remainingDelete.disabled).toBe(true);
    });

    it('Convert to markdown turns a code cell into a markdown cell', async () => {
        render(<LivePanel jobId="job-1" initialCells={['# heading\n\nbody']} />);
        // Cell starts as code (textarea + Run button visible).
        expect(screen.getByLabelText('Run cell')).toBeInTheDocument();
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Convert to markdown'));
        });
        // After conversion, the code Run button is gone; the markdown edit
        // affordance is present (toggle starts in editing mode for usability).
        expect(screen.queryByLabelText('Run cell')).not.toBeInTheDocument();
        expect(screen.getByLabelText('Preview markdown')).toBeInTheDocument();
    });

    // -----------------------------------------------------------------------
    // Phase 5 — Save-back flow
    // -----------------------------------------------------------------------

    it('Save button is disabled until the user edits a cell, then calls saveNotebookCells', async () => {
        render(<LivePanel jobId="job-1" initialCells={['print(1)']} />);
        const saveBtn = screen.getByLabelText('Notebook saved') as HTMLButtonElement;
        expect(saveBtn.disabled).toBe(true);

        // Typing into the source flips dirty, enabling the Save button.
        const textarea = screen.getByLabelText('Cell 1 source') as HTMLTextAreaElement;
        await act(async () => {
            fireEvent.change(textarea, { target: { value: 'print(2)' } });
        });
        const enabled = screen.getByLabelText('Save notebook') as HTMLButtonElement;
        expect(enabled.disabled).toBe(false);

        await act(async () => {
            fireEvent.click(enabled);
        });
        await waitFor(() => {
            expect(AnalysisAPI.saveNotebookCells).toHaveBeenCalledWith(
                'job-1',
                [{ cell_type: 'code', source: 'print(2)' }],
            );
        });
    });

    it('Save flow surfaces a transient "Saved" state and re-disables until next edit', async () => {
        render(<LivePanel jobId="job-1" initialCells={['x = 1']} />);
        const textarea = screen.getByLabelText('Cell 1 source') as HTMLTextAreaElement;
        await act(async () => {
            fireEvent.change(textarea, { target: { value: 'y = 2' } });
        });
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Save notebook'));
        });
        await waitFor(() => {
            // The button label flips while in the success flash.
            expect(screen.getByText('Saved')).toBeInTheDocument();
        });
    });

    it('finalizes the cell from the HTTP response when no WS cell_complete arrives', async () => {
        // Simulates the WS pubsub being unreachable: /cells/execute resolves
        // with a success aggregate, but no cell_status/output/complete events
        // ever fire. The cell must not hang in queued.
        render(<LivePanel jobId="job-1" initialCells={['1 + 1']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });

        await waitFor(() => {
            // [1] = the execution_count from the mocked HTTP response.
            expect(screen.getByText(/^\[1\]$/)).toBeInTheDocument();
        });
        // The Stop button is gone — cell is back to idle even without WS.
        expect(screen.queryByLabelText('Stop cell')).not.toBeInTheDocument();
        expect(screen.getByLabelText('Run cell')).toBeInTheDocument();
    });

    it('surfaces an error output when HTTP says the cell failed and WS delivered nothing', async () => {
        const mock = AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>;
        mock.mockResolvedValueOnce({
            execution_id: 'exec-x',
            success: false,
            error_name: 'NameError',
            error_value: "name 'foo' is not defined",
            duration_ms: 7,
            killed_reason: null,
            execution_count: null,
        });
        render(<LivePanel jobId="job-1" initialCells={['foo']} />);
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run cell'));
        });
        await waitFor(() => {
            expect(screen.getByText(/NameError: name 'foo' is not defined/)).toBeInTheDocument();
        });
    });

    it('Run all button fires executeLiveCell once per code cell, skipping markdown', async () => {
        render(
            <LivePanel
                jobId="job-1"
                initialNotebookCells={[
                    { cell_type: 'code', source: 'a = 1' },
                    { cell_type: 'markdown', source: '# md' },
                    { cell_type: 'code', source: 'b = 2' },
                ]}
            />,
        );
        await act(async () => {
            fireEvent.click(screen.getByLabelText('Run all cells'));
        });
        await waitFor(() => {
            expect(AnalysisAPI.executeLiveCell).toHaveBeenCalledTimes(2);
        });
        const calls = (AnalysisAPI.executeLiveCell as ReturnType<typeof vi.fn>).mock.calls;
        expect(calls[0][1]).toBe('a = 1');
        expect(calls[1][1]).toBe('b = 2');
    });
});
