import type { ColumnDtype, ColumnRole } from '../api';

/** Token name (CSS variable) keyed by column role. */
export const ROLE_COLOR_VAR: Record<ColumnRole, string> = {
    target: '--bg-turquoise-surf',
    metric: '--bg-turquoise-surf',
    dim: '--accent-violet',
    time: '--bg-blue-green',
    pii: '--status-warn',
    other: '--text-secondary',
};

/** Token name (CSS variable) keyed by dtype. */
export const DTYPE_COLOR_VAR: Record<ColumnDtype, string> = {
    int: '--bg-turquoise-surf',
    float: '--bg-turquoise-surf',
    datetime: '--bg-blue-green',
    category: '--accent-violet',
    bool: '--status-warn',
    text: '--text-secondary',
};

/** Convenience helpers returning a ``var(...)`` string usable in style props. */
export const roleVar = (role: ColumnRole): string => `var(${ROLE_COLOR_VAR[role] ?? '--text-secondary'})`;
export const dtypeVar = (dtype: ColumnDtype): string => `var(${DTYPE_COLOR_VAR[dtype] ?? '--text-secondary'})`;

/** Status colour for phase/sub-step/agent dots. */
export const STATUS_COLOR_VAR = {
    queued: '--text-dim',
    running: '--bg-turquoise-surf',
    done: '--status-good',
    failed: '--status-bad',
} as const;

export const statusVar = (status: keyof typeof STATUS_COLOR_VAR): string =>
    `var(${STATUS_COLOR_VAR[status]})`;
