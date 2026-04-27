import type { FC } from 'react';

interface DonutSlice {
    label: string;
    value: number;
    color: string;
}

interface DonutProps {
    slices: DonutSlice[];
    size?: number;
    thickness?: number;
    ariaLabel?: string;
}

/** Compact donut chart in pure SVG, used by the cost breakdown panel. */
export const Donut: FC<DonutProps> = ({ slices, size = 72, thickness = 12, ariaLabel }) => {
    const total = slices.reduce((sum, s) => sum + Math.max(0, s.value), 0);
    const radius = (size - thickness) / 2;
    const circumference = 2 * Math.PI * radius;

    if (total === 0) {
        return (
            <svg
                width={size}
                height={size}
                role="img"
                aria-label={ariaLabel ?? 'empty donut'}
            >
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="var(--text-dim)"
                    strokeWidth={thickness}
                />
            </svg>
        );
    }

    let offset = 0;
    return (
        <svg
            width={size}
            height={size}
            role="img"
            aria-label={
                ariaLabel ?? `donut with ${slices.length} slices totalling ${total.toFixed(2)}`
            }
            viewBox={`0 0 ${size} ${size}`}
        >
            <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
                {slices.map((s, i) => {
                    const fraction = Math.max(0, s.value) / total;
                    const dash = fraction * circumference;
                    const arc = (
                        <circle
                            key={i}
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            fill="none"
                            stroke={s.color}
                            strokeWidth={thickness}
                            strokeDasharray={`${dash} ${circumference - dash}`}
                            strokeDashoffset={-offset}
                        />
                    );
                    offset += dash;
                    return arc;
                })}
            </g>
        </svg>
    );
};
