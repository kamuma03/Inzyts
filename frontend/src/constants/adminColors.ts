import type { UserRole } from '../api';

/** Role pill colours used by the admin-users selector. */
export const ROLE_COLORS: Record<UserRole, string> = {
    admin: 'bg-red-500/20 text-red-400 border-red-500/30',
    analyst: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    viewer: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

/** Audit-log action token colours. ``text-slate-300`` is the fallback
 *  for any action not listed here. */
export const ACTION_COLORS: Record<string, string> = {
    login: 'text-green-400',
    login_failed: 'text-red-400',
    start_analysis: 'text-blue-400',
    upload_file: 'text-yellow-400',
    create_user: 'text-purple-400',
    update_user: 'text-purple-400',
    delete_user: 'text-red-400',
};
