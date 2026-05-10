import { type FC } from 'react';

interface SkeletonProps {
    /** Tailwind-arbitrary or CSS height (default 12px). */
    height?: string;
    /** Tailwind-arbitrary or CSS width (default 100%). */
    width?: string;
    /** Corner rounding token. */
    rounded?: 'none' | 'sm' | 'md' | 'full';
    className?: string;
}

const ROUNDED: Record<NonNullable<SkeletonProps['rounded']>, string> = {
    none: 'rounded-none',
    sm: 'rounded-sm',
    md: 'rounded-md',
    full: 'rounded-full',
};

/** Single shape-of-content placeholder bar. Carries the existing `.skeleton`
 *  utility (animated shimmer) and an inline-style fallback for arbitrary
 *  width/height. Mirror the real layout when composing — same line counts,
 *  same column structure — so the skeleton is a true preview rather than
 *  a generic loader.
 *
 *  Don't use for opaque ops (upload, export) — `<Spinner>` or
 *  `<ProgressPill>` is the right primitive there. */
export const Skeleton: FC<SkeletonProps> = ({
    height = '12px',
    width = '100%',
    rounded = 'sm',
    className = '',
}) => (
    <div
        aria-hidden="true"
        style={{ height, width }}
        className={`skeleton ${ROUNDED[rounded]} ${className}`.trim()}
    />
);

interface SkeletonLineProps {
    /** Number of stacked lines (default 3). Last line is shortened so the
     *  block reads as "wrapped paragraph" rather than a column. */
    lines?: number;
    /** Pixel gap between lines (default 6). */
    gap?: number;
    className?: string;
}

/** Stack of skeleton lines with varied widths — the simplest "paragraph"
 *  shape. Uses a deterministic pattern so renders are stable across
 *  re-mounts. */
export const SkeletonLine: FC<SkeletonLineProps> = ({
    lines = 3,
    gap = 6,
    className = '',
}) => {
    // Deterministic widths cycling through 100/95/85/70 percent so the
    // last line lands shorter regardless of `lines` value.
    const widths = ['100%', '95%', '85%', '70%'];
    return (
        <div
            className={`flex flex-col ${className}`.trim()}
            style={{ gap: `${gap}px` }}
            aria-hidden="true"
        >
            {Array.from({ length: lines }).map((_, i) => {
                const isLast = i === lines - 1;
                const width = isLast && lines > 1 ? widths[3] : widths[i % widths.length];
                return <Skeleton key={i} width={width} />;
            })}
        </div>
    );
};

type SkeletonCardVariant = 'job' | 'summary' | 'row' | 'notebook';

interface SkeletonCardProps {
    variant: SkeletonCardVariant;
    className?: string;
}

/** Pre-shaped skeleton for the most common card layouts in the app. Each
 *  variant intentionally mirrors the layout of its concrete counterpart
 *  (JobHistory card, executive-summary card, data table row, notebook
 *  waiting state) so the swap to real content lands without a layout
 *  shift. */
export const SkeletonCard: FC<SkeletonCardProps> = ({ variant, className = '' }) => {
    if (variant === 'job') {
        return (
            <div className={`p-3 rounded-md border border-[var(--rule)] bg-white/[0.03] ${className}`.trim()} aria-hidden="true">
                <div className="flex items-center gap-2 mb-2">
                    <Skeleton height="6px" width="6px" rounded="full" />
                    <Skeleton height="14px" width="60%" />
                </div>
                <div className="flex items-center gap-2">
                    <Skeleton height="12px" width="20%" />
                    <Skeleton height="12px" width="30%" />
                </div>
            </div>
        );
    }

    if (variant === 'summary') {
        return (
            <div className={`flex flex-col gap-3 ${className}`.trim()} aria-hidden="true">
                <Skeleton height="16px" width="40%" />
                <SkeletonLine lines={2} />
                <div className="grid grid-cols-2 gap-3 mt-1">
                    <SkeletonLine lines={3} gap={4} />
                    <SkeletonLine lines={3} gap={4} />
                </div>
            </div>
        );
    }

    if (variant === 'row') {
        return (
            <div className={`grid grid-cols-4 gap-3 px-3 py-2 ${className}`.trim()} aria-hidden="true">
                <Skeleton height="12px" width="80%" />
                <Skeleton height="12px" width="60%" />
                <Skeleton height="12px" width="50%" />
                <Skeleton height="12px" width="40%" />
            </div>
        );
    }

    // notebook — header line + paragraph + 2-col bullet grid
    return (
        <div className={`flex flex-col gap-2 ${className}`.trim()} aria-hidden="true">
            <Skeleton height="16px" width="40%" />
            <Skeleton height="12px" width="100%" />
            <Skeleton height="12px" width="92%" />
            <div className="grid grid-cols-2 gap-3 mt-2">
                <div className="flex flex-col gap-1.5">
                    <Skeleton height="10px" width="50%" />
                    <Skeleton height="10px" width="100%" />
                    <Skeleton height="10px" width="85%" />
                    <Skeleton height="10px" width="70%" />
                </div>
                <div className="flex flex-col gap-1.5">
                    <Skeleton height="10px" width="50%" />
                    <Skeleton height="10px" width="100%" />
                    <Skeleton height="10px" width="65%" />
                    <Skeleton height="10px" width="85%" />
                </div>
            </div>
        </div>
    );
};

interface SkeletonListProps {
    /** Number of cards to render (default 4). */
    rows?: number;
    variant?: SkeletonCardVariant;
    /** Pixel gap between cards (default 8). */
    gap?: number;
    className?: string;
}

/** Repeat of `SkeletonCard` — the canonical "loading list" shape. Use for
 *  job history, search results, anywhere a list of N similar items is
 *  about to arrive. */
export const SkeletonList: FC<SkeletonListProps> = ({
    rows = 4,
    variant = 'job',
    gap = 8,
    className = '',
}) => (
    <div
        className={`flex flex-col ${className}`.trim()}
        style={{ gap: `${gap}px` }}
        role="status"
        aria-label="Loading"
    >
        {Array.from({ length: rows }).map((_, i) => (
            <SkeletonCard key={i} variant={variant} />
        ))}
    </div>
);
