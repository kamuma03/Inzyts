import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AnalysisAPI, AuditLogRecord } from '../api';
import { ACTION_COLORS } from '../constants/adminColors';
import { DataTableShell } from '../components/DataTableShell';
import { getErrorMessage } from '../utils/errorMessage';

export const AdminAuditPage: React.FC = () => {
    const [logs, setLogs] = useState<AuditLogRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Filters
    const [filterUsername, setFilterUsername] = useState('');
    const [filterAction, setFilterAction] = useState('');

    // Monotonic request id — only the most recent fetch is allowed to write
    // results, so a slow stale response can't clobber a newer one.
    const requestSeqRef = useRef(0);

    const loadLogs = useCallback(async () => {
        const seq = ++requestSeqRef.current;
        setLoading(true);
        try {
            const params: Record<string, string> = { limit: '100' };
            if (filterUsername) params.username = filterUsername;
            if (filterAction) params.action = filterAction;
            const data = await AnalysisAPI.getAuditLogs(params);
            if (seq !== requestSeqRef.current) return; // a newer request superseded this one
            setLogs(data);
            setError('');
        } catch (err) {
            if (seq !== requestSeqRef.current) return;
            setError(getErrorMessage(err, 'Failed to load audit logs'));
        } finally {
            if (seq === requestSeqRef.current) setLoading(false);
        }
    }, [filterUsername, filterAction]);

    // Debounce filter-driven refetches (~300ms) so typing in the username
    // field doesn't fire a request per keystroke. The latest-wins guard above
    // still protects against out-of-order responses.
    useEffect(() => {
        const t = setTimeout(() => { loadLogs(); }, 300);
        return () => clearTimeout(t);
    }, [loadLogs]);

    const formatTimestamp = (ts: string | null) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return d.toLocaleString();
    };

    return (
        <div className="p-6 max-w-6xl mx-auto">
            <h2 className="text-[1.4rem] font-semibold text-[var(--text-primary)] mb-6">Audit logs</h2>

            {error && (
                <div className="mb-4 p-3 bg-[color-mix(in_srgb,var(--bad)_10%,transparent)] border border-[color-mix(in_srgb,var(--bad)_30%,transparent)] rounded-md text-[var(--bad)] text-sm">
                    {error}
                </div>
            )}

            {/* Filters */}
            <div className="flex gap-3 mb-4">
                <input
                    type="text" placeholder="Filter by username"
                    value={filterUsername} onChange={e => setFilterUsername(e.target.value)}
                    className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] placeholder:text-[var(--text-dim)] text-sm w-48"
                />
                <select
                    value={filterAction} onChange={e => setFilterAction(e.target.value)}
                    className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] text-sm"
                >
                    <option value="">All actions</option>
                    <option value="login">Login</option>
                    <option value="login_failed">Failed Login</option>
                    <option value="start_analysis">Start Analysis</option>
                    <option value="upload_file">Upload File</option>
                    <option value="create_user">Create User</option>
                    <option value="update_user">Update User</option>
                    <option value="delete_user">Delete User</option>
                </select>
                <button
                    onClick={loadLogs}
                    className="px-4 py-2 bg-[var(--surface-2)] hover:bg-[var(--rule-strong)] text-[var(--text-primary)] border border-[var(--rule)] rounded-md text-sm transition-colors"
                >
                    Refresh
                </button>
            </div>

            {loading ? (
                <div className="text-[var(--text-secondary)] text-center py-12">Loading audit logs…</div>
            ) : logs.length === 0 ? (
                <div className="text-[var(--text-dim)] text-center py-12">No audit log entries found.</div>
            ) : (
                <DataTableShell
                    columns={['Timestamp', 'User', 'Action', 'Detail', 'IP', 'Status']}
                    padding="sm"
                    wrapperClass="overflow-x-auto"
                >
                    {logs.map(log => (
                        <tr key={log.id} className="border-b border-[var(--rule)] hover:bg-white/[0.03]">
                            <td className="px-3 py-2 text-[var(--text-secondary)] text-xs whitespace-nowrap">
                                {formatTimestamp(log.timestamp)}
                            </td>
                            <td className="px-3 py-2 text-[var(--text-primary)] text-xs">{log.username || '—'}</td>
                            <td className="px-3 py-2">
                                <span className={`text-xs font-medium ${ACTION_COLORS[log.action] || 'text-[var(--text-secondary)]'}`}>
                                    {log.action}
                                </span>
                            </td>
                            <td className="px-3 py-2 text-[var(--text-secondary)] text-xs max-w-xs truncate" title={log.detail || ''}>
                                {log.detail || '—'}
                            </td>
                            <td className="px-3 py-2 text-[var(--text-dim)] text-xs">{log.ip_address || '—'}</td>
                            <td className="px-3 py-2 text-[var(--text-dim)] text-xs">{log.status_code || '—'}</td>
                        </tr>
                    ))}
                </DataTableShell>
            )}
        </div>
    );
};

export default AdminAuditPage;
