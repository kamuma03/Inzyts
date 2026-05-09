import type { ColumnDtype, ColumnRole } from '../api';

/** Token name (CSS variable) keyed by column role. */
export const ROLE_COLOR_VAR: Record<ColumnRole, string> = {
    target: '--accent',
    metric: '--accent',
    dim: '--accent-violet',
    time: '--accent',
    pii: '--warn',
    other: '--text-secondary',
};

/** Token name (CSS variable) keyed by dtype. */
export const DTYPE_COLOR_VAR: Record<ColumnDtype, string> = {
    int: '--accent',
    float: '--accent',
    datetime: '--accent',
    category: '--accent-violet',
    bool: '--warn',
    text: '--text-secondary',
};

/** Convenience helpers returning a ``var(...)`` string usable in style props. */
export const roleVar = (role: ColumnRole): string => `var(${ROLE_COLOR_VAR[role] ?? '--text-secondary'})`;
export const dtypeVar = (dtype: ColumnDtype): string => `var(${DTYPE_COLOR_VAR[dtype] ?? '--text-secondary'})`;

/** Status colour for phase/sub-step/agent dots. */
export const STATUS_COLOR_VAR = {
    queued: '--text-dim',
    running: '--accent',
    done: '--ok',
    failed: '--bad',
} as const;

export const statusVar = (status: keyof typeof STATUS_COLOR_VAR): string =>
    `var(${STATUS_COLOR_VAR[status]})`;
