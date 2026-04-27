import type { FC } from 'react';

interface SparklineProps {
    values: number[];
    width?: number;
    height?: number;
    stroke?: string;
    fill?: string;
    ariaLabel?: string;
}

/** Pure-SVG sparkline. No chart library — keeps the bundle small. */
export const Sparkline: FC<SparklineProps> = ({
    values,
    width = 80,
    height = 18,
    stroke = 'var(--bg-turquoise-surf)',
    fill = 'transparent',
    ariaLabel,
}) => {
    if (!values || values.length === 0) {
        return (
            <svg
                width={width}
                height={height}
                role="img"
                aria-label={ariaLabel ?? 'no data'}
            />
        );
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const stepX = values.length > 1 ? width / (values.length - 1) : 0;

    const points = values
        .map((v, i) => {
            const x = i * stepX;
            const y = height - ((v - min) / range) * height;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join(' ');

    return (
        <svg
            width={width}
            height={height}
            role="img"
            aria-label={ariaLabel ?? `sparkline of ${values.length} values`}
        >
            <polyline
                points={points}
                fill={fill}
                stroke={stroke}
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
            />
        </svg>
    );
};
