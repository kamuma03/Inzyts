import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { ColumnInspector } from './ColumnInspector';
import type { ColumnProfile } from '../../api';

vi.mock('../../api', async () => {
    const actual = await vi.importActual<typeof import('../../api')>('../../api');
    return {
        ...actual,
        CommandCenterAPI: {
            getColumns: vi.fn(),
            getCost: vi.fn(),
        },
    };
});

import { CommandCenterAPI } from '../../api';

const fakeColumns: ColumnProfile[] = [
    {
        name: 'price',
        dtype: 'float',
        cardinality_or_range: '0–999',
        role: 'metric',
        null_count: 0,
        histogram: [0.1, 0.2, 0.4, 0.7, 0.9, 0.5, 0.3, 0.1],
        stats: { mean: 42.5, median: 38, min: 0, max: 999 },
    },
    {
        name: 'churn',
        dtype: 'bool',
        cardinality_or_range: '2 levels',
        role: 'target',
        null_count: 5,
        histogram: [],
        stats: null,
    },
];

describe('ColumnInspector', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (CommandCenterAPI.getColumns as ReturnType<typeof vi.fn>).mockResolvedValue(fakeColumns);
    });

    it('renders all columns from the API', async () => {
        render(
            <ColumnInspector jobId="job-render" selectedColumn={null} onSelect={vi.fn()} />,
        );
        await waitFor(() => {
            expect(screen.getByText('price')).toBeInTheDocument();
            expect(screen.getByText('churn')).toBeInTheDocument();
        });
    });

    it('shows the prompt to select a column when none is selected', async () => {
        render(
            <ColumnInspector jobId="job-prompt" selectedColumn={null} onSelect={vi.fn()} />,
        );
        await waitFor(() => expect(screen.getByText('price')).toBeInTheDocument());
        expect(screen.getByText(/select a column/i)).toBeInTheDocument();
    });

    it('shows detail card for the selected column without an extra fetch', async () => {
        const { rerender } = render(
            <ColumnInspector jobId="job-detail" selectedColumn={null} onSelect={vi.fn()} />,
        );
        await waitFor(() => expect(screen.getByText('price')).toBeInTheDocument());

        // Switch selection — no second API call should fire (same jobId, cached).
        rerender(
            <ColumnInspector jobId="job-detail" selectedColumn="price" onSelect={vi.fn()} />,
        );

        // Detail card shows mean
        expect(screen.getByText('mean')).toBeInTheDocument();
        expect(CommandCenterAPI.getColumns).toHaveBeenCalledTimes(1);
    });

    it('clicking a row calls onSelect with that column', async () => {
        const onSelect = vi.fn();
        render(
            <ColumnInspector jobId="job-2" selectedColumn={null} onSelect={onSelect} />,
        );
        await waitFor(() => expect(screen.getByText('churn')).toBeInTheDocument());
        await act(async () => {
            fireEvent.click(screen.getByText('churn'));
        });
        expect(onSelect).toHaveBeenCalledWith('churn');
    });
});
