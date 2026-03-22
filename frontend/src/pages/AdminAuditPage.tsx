import React, { useState, useEffect, useCallback } from 'react';
import { AnalysisAPI, AuditLogRecord } from '../api';

const ACTION_COLORS: Record<string, string> = {
    login: 'text-green-400',
    login_failed: 'text-red-400',
    start_analysis: 'text-blue-400',
    upload_file: 'text-yellow-400',
    create_user: 'text-purple-400',
    update_user: 'text-purple-400',
    delete_user: 'text-red-400',
};

export const AdminAuditPage: React.FC = () => {
    const [logs, setLogs] = useState<AuditLogRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Filters
    const [filterUsername, setFilterUsername] = useState('');
    const [filterAction, setFilterAction] = useState('');

    const loadLogs = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, string> = { limit: '100' };
            if (filterUsername) params.username = filterUsername;
            if (filterAction) params.action = filterAction;
            const data = await AnalysisAPI.getAuditLogs(params);
            setLogs(data);
            setError('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load audit logs');
        } finally {
            setLoading(false);
        }
    }, [filterUsername, filterAction]);

    useEffect(() => { loadLogs(); }, [loadLogs]);

    const formatTimestamp = (ts: string | null) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return d.toLocaleString();
    };

    return (
        <div className="p-6 max-w-6xl mx-auto">
            <h2 className="text-2xl font-bold text-white mb-6">Audit Logs</h2>

            {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
                    {error}
                </div>
            )}

            {/* Filters */}
            <div className="flex gap-3 mb-4">
                <input
                    type="text" placeholder="Filter by username"
                    value={filterUsername} onChange={e => setFilterUsername(e.target.value)}
                    className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm w-48"
                />
                <select
                    value={filterAction} onChange={e => setFilterAction(e.target.value)}
                    className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm"
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
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm"
                >
                    Refresh
                </button>
            </div>

            {loading ? (
                <div className="text-slate-400 text-center py-12">Loading audit logs...</div>
            ) : logs.length === 0 ? (
                <div className="text-slate-500 text-center py-12">No audit log entries found.</div>
            ) : (
                <div className="bg-slate-800/40 rounded-xl border border-slate-700/50 overflow-hidden overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-700/50 text-slate-400 text-left">
                                <th className="px-3 py-3 font-medium">Timestamp</th>
                                <th className="px-3 py-3 font-medium">User</th>
                                <th className="px-3 py-3 font-medium">Action</th>
                                <th className="px-3 py-3 font-medium">Detail</th>
                                <th className="px-3 py-3 font-medium">IP</th>
                                <th className="px-3 py-3 font-medium">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {logs.map(log => (
                                <tr key={log.id} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                                    <td className="px-3 py-2 text-slate-400 text-xs whitespace-nowrap">
                                        {formatTimestamp(log.timestamp)}
                                    </td>
                                    <td className="px-3 py-2 text-white text-xs">{log.username || '—'}</td>
                                    <td className="px-3 py-2">
                                        <span className={`text-xs font-medium ${ACTION_COLORS[log.action] || 'text-slate-300'}`}>
                                            {log.action}
                                        </span>
                                    </td>
                                    <td className="px-3 py-2 text-slate-400 text-xs max-w-xs truncate" title={log.detail || ''}>
                                        {log.detail || '—'}
                                    </td>
                                    <td className="px-3 py-2 text-slate-500 text-xs">{log.ip_address || '—'}</td>
                                    <td className="px-3 py-2 text-slate-500 text-xs">{log.status_code || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default AdminAuditPage;
