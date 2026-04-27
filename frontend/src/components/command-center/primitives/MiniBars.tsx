import type { FC } from 'react';

interface MiniBarsProps {
    values: number[];
    width?: number;
    height?: number;
    color?: string;
    gap?: number;
    ariaLabel?: string;
}

/** Inline bar chart. Each value should be in [0, 1]; values are clamped. */
export const MiniBars: FC<MiniBarsProps> = ({
    values,
    width = 56,
    height = 18,
    color = 'var(--bg-turquoise-surf)',
    gap = 1,
    ariaLabel,
}) => {
    if (!values || values.length === 0) {
        return (
            <svg
                width={width}
                height={height}
                role="img"
                aria-label={ariaLabel ?? 'no distribution data'}
            />
        );
    }
    const total = values.length;
    const barW = Math.max(1, (width - gap * (total - 1)) / total);

    return (
        <svg
            width={width}
            height={height}
            role="img"
            aria-label={ariaLabel ?? `distribution across ${total} bins`}
        >
            {values.map((raw, i) => {
                const v = Math.max(0, Math.min(1, raw));
                const h = Math.max(1, v * height);
                const x = i * (barW + gap);
                const y = height - h;
                return (
                    <rect
                        key={i}
                        x={x}
                        y={y}
                        width={barW}
                        height={h}
                        fill={color}
                        opacity={0.85}
                    />
                );
            })}
        </svg>
    );
};
