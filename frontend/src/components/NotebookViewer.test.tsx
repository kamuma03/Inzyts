import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { NotebookViewer } from './NotebookViewer';
import type { UseSocketHandlers } from '../hooks/useSocket';

// ---------------------------------------------------------------------------
// API mocks — supply summary, PII, and cells endpoints used by the viewer.
// Fixtures live inside the factory because vi.mock is hoisted to the top of
// the file before any top-level `const` is initialized.
// ---------------------------------------------------------------------------

vi.mock('../api', () => {
    const summary = {
        key_findings: ['Finding A', 'Finding B'],
        data_quality_highlights: ['DQ A'],
        recommendations: ['Reco A'],
        summary_text: 'A short executive summary blurb for the analysis.',
        generated_by: 'llm',
    };
    const piiScan = { has_pii: false, findings: [], scanned_cells: 4 };
    const notebookCells = {
        cells: [
            { cell_type: 'markdown', source: '# Title\n\nIntro paragraph.', outputs: [] },
            { cell_type: 'code', source: 'print("hello")', outputs: [] },
        ],
        job_id: 'job-1',
    };
    return {
        AnalysisAPI: {
            getExecutiveSummary: vi.fn().mockResolvedValue(summary),
            getPIIScan: vi.fn().mockResolvedValue(piiScan),
            getNotebookCells: vi.fn().mockResolvedValue(notebookCells),
            getConversationHistory: vi.fn().mockResolvedValue({ messages: [] }),
            executeLiveCell: vi.fn(),
            editCell: vi.fn(),
            restartLiveKernel: vi.fn(),
            interruptLiveKernel: vi.fn(),
            exportReport: vi.fn(),
            downloadNotebook: vi.fn(),
            askFollowUp: vi.fn(),
        },
    };
});

let _capturedHandlers: UseSocketHandlers | undefined;
vi.mock('../hooks/useSocket', () => ({
    useSocket: (_jobId: string | null, handlers?: UseSocketHandlers) => {
        _capturedHandlers = handlers;
        return { logs: [], events: [], progress: null, metrics: null, phases: null, isConnected: false };
    },
}));

// CodeMirror requires DOM measurement APIs jsdom does not implement — swap
// in a textarea so the cell stack renders.
vi.mock('./command-center/panels/live/CellSourceEditor', () => ({
    CellSourceEditor: ({ value, onChange, ariaLabel }: {
        value: string;
        onChange: (v: string) => void;
        ariaLabel: string;
    }) => (
        <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            aria-label={ariaLabel}
        />
    ),
}));

import { AnalysisAPI } from '../api';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('NotebookViewer', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('exposes only Report and Notebook tabs (no Static/Interactive/Live)', async () => {
        await act(async () => {
            render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);
        });

        expect(screen.getByRole('button', { name: /^Report$/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^Notebook$/ })).toBeInTheDocument();
        // Old labels must be gone.
        expect(screen.queryByRole('button', { name: /^Editor$/ })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /^Sandbox$/ })).not.toBeInTheDocument();
    });

    it('defaults to the Report tab and renders only the executive summary', async () => {
        await act(async () => {
            render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);
        });

        await waitFor(() => {
            expect(screen.getByText('Executive Summary')).toBeInTheDocument();
        });
        expect(screen.getByText('A short executive summary blurb for the analysis.')).toBeInTheDocument();
        expect(screen.getByText('Finding A')).toBeInTheDocument();
        expect(screen.getByText('Reco A')).toBeInTheDocument();

        // The Report tab must NOT render notebook cells.
        expect(AnalysisAPI.getNotebookCells).not.toHaveBeenCalled();
    });

    it('switching to Notebook tab fetches cells and renders the LivePanel', async () => {
        await act(async () => {
            render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);
        });

        await waitFor(() => {
            expect(AnalysisAPI.getExecutiveSummary).toHaveBeenCalled();
        });

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /^Notebook$/ }));
        });

        await waitFor(() => {
            expect(AnalysisAPI.getNotebookCells).toHaveBeenCalledWith('job-1');
        });

        // Code cell from the fixture appears as an editable textarea.
        await waitFor(() => {
            const sourceFields = screen.getAllByLabelText(/Cell \d+ source|Markdown cell \d+ source/);
            expect(sourceFields.length).toBeGreaterThan(0);
        });
    });

    it('shows the waiting state when status is not completed', () => {
        render(<NotebookViewer jobId="job-1" resultPath={null} status="running" />);
        expect(screen.getByText(/Analysis in progress/)).toBeInTheDocument();
        expect(AnalysisAPI.getExecutiveSummary).not.toHaveBeenCalled();
    });
});
