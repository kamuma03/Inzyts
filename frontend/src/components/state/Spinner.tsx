import { type FC } from 'react';
import { Loader2 } from 'lucide-react';

type SpinnerSize = 'sm' | 'md';

interface SpinnerProps {
    /** sm (14px) inline-with-text · md (28px) panel-centered. */
    size?: SpinnerSize;
    /** Required for size="md"; optional for size="sm". Verb form with
     *  ellipsis: "Generating PDF…", "Uploading…", "Testing connection…". */
    caption?: string;
    className?: string;
}

const PIXELS: Record<SpinnerSize, number> = { sm: 14, md: 28 };

/** Opaque-operation indicator — for ops where the result has no
 *  preview-able shape (file upload, export, db connection test, login).
 *  When you DO know the shape of what's coming, prefer `<Skeleton>` —
 *  it lands faster perceptually even at identical wall-clock time.
 *
 *  Track in `--rule`, head in `--accent`, always. md is panel-centered
 *  with a caption; sm is inline-with-text and the caption is optional. */
export const Spinner: FC<SpinnerProps> = ({ size = 'md', caption, className = '' }) => {
    const px = PIXELS[size];
    const layout =
        size === 'md'
            ? 'flex flex-col items-center justify-center gap-2'
            : 'inline-flex items-center gap-1.5';
    const captionClass =
        size === 'md'
            ? 'text-[12px] text-[var(--text-secondary)]'
            : 'text-[12px] text-[var(--text-dim)]';

    return (
        <div
            role="status"
            aria-live="polite"
            aria-label={caption ?? 'Loading'}
            className={`${layout} ${className}`.trim()}
        >
            <Loader2
                size={px}
                className="animate-spin text-[var(--accent)]"
                strokeWidth={2}
            />
            {caption && <span className={captionClass}>{caption}</span>}
        </div>
    );
};

/** Alias for `<Spinner size="sm" />` — the inline-with-text variant. */
export const InlineSpinner: FC<{ caption?: string; className?: string }> = ({ caption, className }) => (
    <Spinner size="sm" caption={caption} className={className} />
);
