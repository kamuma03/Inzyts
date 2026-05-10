import type { UserRole } from '../api';

/** Role pill colours used by the admin-users selector. Each role gets a
 *  status hue plus a soft tinted background and a subtle border in the
 *  same family. `analyst` borrows --accent (functional/primary).
 *  `admin` is a high-permission state, hence --bad. `viewer` is neutral
 *  and uses the dim text colour against a transparent fill. */
export const ROLE_COLORS: Record<UserRole, string> = {
    admin: 'bg-[color-mix(in_srgb,var(--bad)_20%,transparent)] text-[var(--bad)] border-[color-mix(in_srgb,var(--bad)_30%,transparent)]',
    analyst: 'bg-[var(--accent-soft)] text-[var(--accent)] border-[color-mix(in_srgb,var(--accent)_30%,transparent)]',
    viewer: 'bg-white/[0.04] text-[var(--text-secondary)] border-[var(--rule)]',
};

/** Audit-log action token colours. `text-[var(--text-secondary)]` is the
 *  fallback for any action not listed here. Maps action semantics to
 *  status tokens: success → ok, failure → bad, mutation → warn,
 *  navigation → accent, role-change → accent-violet. */
export const ACTION_COLORS: Record<string, string> = {
    login: 'text-[var(--ok)]',
    login_failed: 'text-[var(--bad)]',
    start_analysis: 'text-[var(--accent)]',
    upload_file: 'text-[var(--warn)]',
    create_user: 'text-[var(--accent-violet)]',
    update_user: 'text-[var(--accent-violet)]',
    delete_user: 'text-[var(--bad)]',
};
