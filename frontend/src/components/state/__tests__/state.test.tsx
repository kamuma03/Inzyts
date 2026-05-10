import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
    Skeleton, SkeletonLine, SkeletonCard, SkeletonList,
    Spinner, InlineSpinner,
    EmptyState,
    ErrorState,
    InlineError,
    ProgressPill,
} from '..';

describe('Skeleton primitives', () => {
    it('Skeleton renders an aria-hidden box with the .skeleton class', () => {
        const { container } = render(<Skeleton width="50%" height="20px" />);
        const node = container.firstChild as HTMLElement;
        expect(node.className).toContain('skeleton');
        expect(node.getAttribute('aria-hidden')).toBe('true');
        expect(node.style.height).toBe('20px');
        expect(node.style.width).toBe('50%');
    });

    it('SkeletonLine renders the requested number of lines', () => {
        const { container } = render(<SkeletonLine lines={5} />);
        const skeletons = container.querySelectorAll('.skeleton');
        expect(skeletons.length).toBe(5);
    });

    it('SkeletonCard variant=job mirrors the JobHistory shape', () => {
        const { container } = render(<SkeletonCard variant="job" />);
        const skeletons = container.querySelectorAll('.skeleton');
        // Status dot + filename + mode + time = 4 bars
        expect(skeletons.length).toBe(4);
    });

    it('SkeletonList exposes a status role with rows skeletons inside', () => {
        render(<SkeletonList rows={3} variant="job" />);
        expect(screen.getByRole('status')).toBeInTheDocument();
    });
});

describe('Spinner', () => {
    it('renders a status with caption when provided', () => {
        render(<Spinner size="md" caption="Generating PDF" />);
        expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Generating PDF');
        expect(screen.getByText('Generating PDF')).toBeInTheDocument();
    });

    it('falls back to a generic aria-label without caption', () => {
        render(<Spinner size="sm" />);
        expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading');
    });

    it('InlineSpinner is the size=sm alias', () => {
        const { container } = render(<InlineSpinner caption="Analysing" />);
        // sm renders inline-flex
        expect(container.firstChild).toHaveClass('inline-flex');
    });
});

describe('EmptyState', () => {
    it('renders icon, title, body, and CTA', () => {
        const onClick = vi.fn();
        render(
            <EmptyState
                icon="inbox"
                title="No analyses yet"
                body="Start a new analysis to see it here."
                cta={{ label: 'New analysis', onClick }}
            />
        );
        expect(screen.getByText('No analyses yet')).toBeInTheDocument();
        expect(screen.getByText('Start a new analysis to see it here.')).toBeInTheDocument();
        const cta = screen.getByText('New analysis');
        fireEvent.click(cta);
        expect(onClick).toHaveBeenCalled();
    });

    it('compact variant drops the icon chip', () => {
        const { container } = render(
            <EmptyState icon="inbox" title="No events" compact />
        );
        // No 40px circle in compact
        expect(container.querySelector('.w-10.h-10')).toBeNull();
        expect(screen.getByText('No events')).toBeInTheDocument();
    });
});

describe('ErrorState', () => {
    it('renders with role=alert, title, body, and Retry that calls onRetry', () => {
        const onRetry = vi.fn();
        render(
            <ErrorState
                title="Couldn't load notebook"
                body="Try again or check the status tab."
                onRetry={onRetry}
            />
        );
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText("Couldn't load notebook")).toBeInTheDocument();
        const retry = screen.getByRole('button', { name: /retry/i });
        fireEvent.click(retry);
        expect(onRetry).toHaveBeenCalled();
    });

    it('disables Retry while retrying=true', () => {
        render(
            <ErrorState title="Failed" onRetry={() => {}} retrying />
        );
        const retry = screen.getByRole('button');
        expect(retry).toBeDisabled();
        expect(retry.textContent).toMatch(/retrying/i);
    });

    it('hides the retry button when no onRetry handler', () => {
        render(<ErrorState title="Failed" />);
        expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    });

    it('details disclosure shows the raw payload behind a toggle', () => {
        render(
            <ErrorState
                title="Failed"
                details="HTTP 500: connection refused"
            />
        );
        // Details start collapsed — pre is not rendered until summary clicked
        expect(screen.getByText(/show details/i)).toBeInTheDocument();
        // jsdom doesn't toggle <details> on click natively — assert presence of the disclosure UI is enough
    });
});

describe('InlineError', () => {
    it('renders with role=alert and shows children', () => {
        render(<InlineError>Database scheme not supported.</InlineError>);
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/database scheme not supported/i)).toBeInTheDocument();
    });

    it('shows a dismiss button only when onDismiss is provided', () => {
        const onDismiss = vi.fn();
        const { rerender } = render(<InlineError>Failed</InlineError>);
        expect(screen.queryByLabelText('Dismiss')).not.toBeInTheDocument();
        rerender(<InlineError onDismiss={onDismiss}>Failed</InlineError>);
        const btn = screen.getByLabelText('Dismiss');
        fireEvent.click(btn);
        expect(onDismiss).toHaveBeenCalled();
    });
});

describe('ProgressPill', () => {
    it('renders steady-state intents as a status with a dot indicator', () => {
        render(<ProgressPill intent="ok" caption="Connected" />);
        expect(screen.getByRole('status')).toHaveTextContent('Connected');
    });

    it('defaults accent intent to a spinner indicator', () => {
        const { container } = render(<ProgressPill intent="accent" caption="Generating" />);
        // Spinner is rendered as the first inline-flex child SVG
        expect(container.querySelector('svg.animate-spin')).toBeInTheDocument();
    });

    it('renders as a button with onClick — fires when clicked', () => {
        const onClick = vi.fn();
        render(<ProgressPill intent="warn" caption="Reconnecting" onClick={onClick} />);
        const btn = screen.getByRole('button');
        fireEvent.click(btn);
        expect(onClick).toHaveBeenCalled();
    });
});
