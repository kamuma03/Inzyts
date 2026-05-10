import React, { useState, useEffect, useCallback } from 'react';
import { AnalysisAPI, UserRecord, UserRole } from '../api';
import { ROLE_COLORS } from '../constants/adminColors';
import { DataTableShell } from '../components/DataTableShell';

export const AdminUsersPage: React.FC = () => {
    const [users, setUsers] = useState<UserRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Create user form
    const [showCreate, setShowCreate] = useState(false);
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newEmail, setNewEmail] = useState('');
    const [newRole, setNewRole] = useState<UserRole>('viewer');
    const [creating, setCreating] = useState(false);

    const loadUsers = useCallback(async () => {
        setLoading(true);
        try {
            const data = await AnalysisAPI.listUsers();
            setUsers(data);
            setError('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load users');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadUsers(); }, [loadUsers]);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            await AnalysisAPI.createUser({
                username: newUsername,
                password: newPassword,
                email: newEmail || undefined,
                role: newRole,
            });
            setNewUsername(''); setNewPassword(''); setNewEmail(''); setNewRole('viewer');
            setShowCreate(false);
            await loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create user');
        } finally {
            setCreating(false);
        }
    };

    const handleRoleChange = async (user: UserRecord, role: UserRole) => {
        try {
            await AnalysisAPI.updateUser(user.id, { role });
            await loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to update role');
        }
    };

    const handleToggleActive = async (user: UserRecord) => {
        try {
            await AnalysisAPI.updateUser(user.id, { is_active: !user.is_active });
            await loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to update user');
        }
    };

    const handleDelete = async (user: UserRecord) => {
        if (!window.confirm(`Delete user "${user.username}"? This cannot be undone.`)) return;
        try {
            await AnalysisAPI.deleteUser(user.id);
            await loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete user');
        }
    };

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-[1.4rem] font-semibold text-[var(--text-primary)]">User management</h2>
                <button
                    onClick={() => setShowCreate(!showCreate)}
                    className="px-4 py-2 bg-[var(--accent)] hover:brightness-110 text-[var(--accent-ink)] rounded-md transition text-sm font-semibold"
                >
                    {showCreate ? 'Cancel' : '+ New user'}
                </button>
            </div>

            {error && (
                <div className="mb-4 p-3 bg-[color-mix(in_srgb,var(--bad)_10%,transparent)] border border-[color-mix(in_srgb,var(--bad)_40%,transparent)] rounded-md text-[var(--bad)] text-sm">
                    {error}
                    <button onClick={() => setError('')} className="ml-2 opacity-70 hover:opacity-100">&times;</button>
                </div>
            )}

            {showCreate && (
                <form onSubmit={handleCreate} className="mb-6 p-4 bg-[var(--surface-2)] rounded-md border border-[var(--rule)] space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                        <input
                            type="text" placeholder="Username" required minLength={2}
                            value={newUsername} onChange={e => setNewUsername(e.target.value)}
                            className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] placeholder:text-[var(--text-dim)] text-sm"
                        />
                        <input
                            type="password" placeholder="Password" required minLength={6}
                            value={newPassword} onChange={e => setNewPassword(e.target.value)}
                            className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] placeholder:text-[var(--text-dim)] text-sm"
                        />
                        <input
                            type="email" placeholder="Email (optional)"
                            value={newEmail} onChange={e => setNewEmail(e.target.value)}
                            className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] placeholder:text-[var(--text-dim)] text-sm"
                        />
                        <select
                            value={newRole} onChange={e => setNewRole(e.target.value as UserRole)}
                            className="px-3 py-2 bg-[rgba(0,0,0,0.2)] border border-[var(--rule)] rounded-md text-[var(--text-primary)] text-sm"
                        >
                            <option value="viewer">Viewer</option>
                            <option value="analyst">Analyst</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <button
                        type="submit" disabled={creating}
                        className="px-4 py-2 bg-[var(--ok)] hover:brightness-110 text-[var(--ok-ink)] rounded-md text-sm font-semibold disabled:opacity-50 transition"
                    >
                        {creating ? 'Creating…' : 'Create user'}
                    </button>
                </form>
            )}

            {loading ? (
                <div className="text-[var(--text-secondary)] text-center py-12">Loading users…</div>
            ) : (
                <DataTableShell
                    columns={['Username', 'Email', 'Role', 'Status', 'Created', { label: 'Actions', align: 'right' }]}
                >
                    {users.map(user => (
                        <tr key={user.id} className="border-b border-[var(--rule)] hover:bg-white/[0.03]">
                            <td className="px-4 py-3 text-[var(--text-primary)] font-medium">{user.username}</td>
                            <td className="px-4 py-3 text-[var(--text-secondary)]">{user.email || '—'}</td>
                            <td className="px-4 py-3">
                                <select
                                    value={user.role}
                                    onChange={e => handleRoleChange(user, e.target.value as UserRole)}
                                    className={`px-2 py-1 rounded border text-xs font-medium ${ROLE_COLORS[user.role]} bg-transparent cursor-pointer`}
                                >
                                    <option value="viewer">Viewer</option>
                                    <option value="analyst">Analyst</option>
                                    <option value="admin">Admin</option>
                                </select>
                            </td>
                            <td className="px-4 py-3">
                                <button
                                    onClick={() => handleToggleActive(user)}
                                    className={`px-2 py-1 rounded text-xs font-medium ${
                                        user.is_active
                                            ? 'bg-[color-mix(in_srgb,var(--ok)_20%,transparent)] text-[var(--ok)]'
                                            : 'bg-[color-mix(in_srgb,var(--warn)_20%,transparent)] text-[var(--warn)]'
                                    }`}
                                >
                                    {user.is_active ? 'Active' : 'Disabled'}
                                </button>
                            </td>
                            <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">
                                {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                            </td>
                            <td className="px-4 py-3 text-right">
                                <button
                                    onClick={() => handleDelete(user)}
                                    className="text-[var(--bad)] hover:brightness-125 text-xs"
                                    title="Delete user"
                                >
                                    Delete
                                </button>
                            </td>
                        </tr>
                    ))}
                </DataTableShell>
            )}
        </div>
    );
};

export default AdminUsersPage;
