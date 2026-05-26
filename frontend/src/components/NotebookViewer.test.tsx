import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { NotebookViewer } from './NotebookViewer';

// ---------------------------------------------------------------------------
// API mocks — fixtures live inside the factory because vi.mock is hoisted.
// ---------------------------------------------------------------------------

vi.mock('../api', () => {
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

vi.mock('../hooks/useSocket', () => ({
    useSocket: () => ({
        logs: [], events: [], progress: null, metrics: null, phases: null, isConnected: false,
    }),
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
// Tests — NotebookViewer is now the Notebook tab's content (no internal
// Report/Notebook toggle; Report is a sibling top-level tab).
// ---------------------------------------------------------------------------

describe('NotebookViewer', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('fetches notebook cells and renders the LivePanel cell stack', async () => {
        render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);

        await waitFor(() => {
            expect(AnalysisAPI.getNotebookCells).toHaveBeenCalledWith('job-1');
        });

        await waitFor(() => {
            const sourceFields = screen.getAllByLabelText(/Cell \d+ source|Markdown cell \d+ source/);
            expect(sourceFields.length).toBeGreaterThan(0);
        });
    });

    it('exposes the Export menu and the Notebook heading', async () => {
        render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);
        await waitFor(() => {
            expect(screen.getByText(/^Notebook$/)).toBeInTheDocument();
        });
        expect(screen.getByRole('button', { name: /^Export$/ })).toBeInTheDocument();
    });

    it('does NOT render the executive summary (that lives in the Report tab now)', async () => {
        render(<NotebookViewer jobId="job-1" resultPath="output/foo.ipynb" status="completed" />);
        await waitFor(() => {
            expect(screen.getByText(/^Notebook$/)).toBeInTheDocument();
        });
        expect(screen.queryByText('Executive Summary')).not.toBeInTheDocument();
    });

    it('shows the waiting state when status is not completed', () => {
        render(<NotebookViewer jobId="job-1" resultPath={null} status="running" />);
        expect(screen.getByText(/Analysis in progress/)).toBeInTheDocument();
        expect(AnalysisAPI.getNotebookCells).not.toHaveBeenCalled();
    });
});
