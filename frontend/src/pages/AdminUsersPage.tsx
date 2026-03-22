import React, { useState, useEffect, useCallback } from 'react';
import { AnalysisAPI, UserRecord, UserRole } from '../api';

const ROLE_COLORS: Record<UserRole, string> = {
    admin: 'bg-red-500/20 text-red-400 border-red-500/30',
    analyst: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    viewer: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

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
                <h2 className="text-2xl font-bold text-white">User Management</h2>
                <button
                    onClick={() => setShowCreate(!showCreate)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors text-sm font-medium"
                >
                    {showCreate ? 'Cancel' : '+ New User'}
                </button>
            </div>

            {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
                    {error}
                    <button onClick={() => setError('')} className="ml-2 text-red-300 hover:text-white">&times;</button>
                </div>
            )}

            {showCreate && (
                <form onSubmit={handleCreate} className="mb-6 p-4 bg-slate-800/60 rounded-xl border border-slate-700/50 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                        <input
                            type="text" placeholder="Username" required minLength={2}
                            value={newUsername} onChange={e => setNewUsername(e.target.value)}
                            className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm"
                        />
                        <input
                            type="password" placeholder="Password" required minLength={6}
                            value={newPassword} onChange={e => setNewPassword(e.target.value)}
                            className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm"
                        />
                        <input
                            type="email" placeholder="Email (optional)"
                            value={newEmail} onChange={e => setNewEmail(e.target.value)}
                            className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm"
                        />
                        <select
                            value={newRole} onChange={e => setNewRole(e.target.value as UserRole)}
                            className="px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm"
                        >
                            <option value="viewer">Viewer</option>
                            <option value="analyst">Analyst</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <button
                        type="submit" disabled={creating}
                        className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                    >
                        {creating ? 'Creating...' : 'Create User'}
                    </button>
                </form>
            )}

            {loading ? (
                <div className="text-slate-400 text-center py-12">Loading users...</div>
            ) : (
                <div className="bg-slate-800/40 rounded-xl border border-slate-700/50 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-700/50 text-slate-400 text-left">
                                <th className="px-4 py-3 font-medium">Username</th>
                                <th className="px-4 py-3 font-medium">Email</th>
                                <th className="px-4 py-3 font-medium">Role</th>
                                <th className="px-4 py-3 font-medium">Status</th>
                                <th className="px-4 py-3 font-medium">Created</th>
                                <th className="px-4 py-3 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map(user => (
                                <tr key={user.id} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                                    <td className="px-4 py-3 text-white font-medium">{user.username}</td>
                                    <td className="px-4 py-3 text-slate-400">{user.email || '—'}</td>
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
                                            className={`px-2 py-1 rounded text-xs font-medium ${user.is_active ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}
                                        >
                                            {user.is_active ? 'Active' : 'Disabled'}
                                        </button>
                                    </td>
                                    <td className="px-4 py-3 text-slate-400 text-xs">
                                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <button
                                            onClick={() => handleDelete(user)}
                                            className="text-red-400 hover:text-red-300 text-xs"
                                            title="Delete user"
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default AdminUsersPage;
