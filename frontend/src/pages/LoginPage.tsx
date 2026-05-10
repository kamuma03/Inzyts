import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader } from 'lucide-react';
import { AnalysisAPI } from '../api';

const LoginPage: React.FC = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        // If already has token, redirect
        const existingToken = sessionStorage.getItem('inzyts_jwt_token');
        if (existingToken) {
            navigate('/');
        }
    }, [navigate]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const data = await AnalysisAPI.login(username, password);
            if (data.access_token) {
                sessionStorage.setItem('inzyts_jwt_token', data.access_token);
                // Redirect to where they were trying to go, or home
                const from = location.state?.from?.pathname || '/';
                navigate(from, { replace: true });
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[var(--surface-0)] flex flex-col items-center justify-center p-4">

            {/* Header/Logo Section */}
            <div className="flex flex-col items-center justify-center mb-12 mt-[-10vh]">
                <div className="flex items-center gap-4 mb-2">
                    <img src="/Inzyts_icon.png" alt="Inzyts Logo" className="w-14 h-14 object-contain" />
                    <h1 className="m-0 text-5xl font-bold text-[var(--text-primary)] font-['Libre_Caslon_Display',serif]">
                        Inzyts
                    </h1>
                </div>
                <h2 className="m-0 text-xl tracking-wide text-[var(--text-secondary)]">
                    Analyze. Predict. Discover.
                </h2>
            </div>

            <div className="bg-[var(--surface-1)]/80 backdrop-blur-md rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.3)] p-8 w-full max-w-[420px] border border-[var(--rule)]/50">
                <form onSubmit={handleSubmit} className="space-y-6">
                    {error && (
                        <div className="p-3 bg-[color-mix(in_srgb,var(--bad)_10%,transparent)] border border-[color-mix(in_srgb,var(--bad)_40%,transparent)] rounded-lg text-[var(--bad)] text-sm flex items-start gap-2">
                            <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{error}</span>
                        </div>
                    )}

                    <div>
                        <label htmlFor="username" className="block text-sm font-medium text-[var(--text-secondary)] mb-2 ml-1">
                            Username
                        </label>
                        <div className="relative">
                            <input
                                type="text"
                                id="username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full px-5 py-3.5 bg-[var(--surface-0)]/50 border border-[var(--rule)] rounded-xl text-[var(--text-primary)] placeholder-[var(--text-secondary)]/50 focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)] outline-none transition-all"
                                placeholder="Enter username"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label htmlFor="password" className="block text-sm font-medium text-[var(--text-secondary)] mb-2 ml-1">
                            Password
                        </label>
                        <div className="relative">
                            <input
                                type="password"
                                id="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-5 py-3.5 bg-[var(--surface-0)]/50 border border-[var(--rule)] rounded-xl text-[var(--text-primary)] placeholder-[var(--text-secondary)]/50 focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)] outline-none transition-all"
                                placeholder="Enter password"
                                required
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full mt-2 bg-[var(--accent)] hover:brightness-110 text-[var(--accent-ink)] font-semibold py-4 px-6 rounded-xl transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center"
                    >
                        {isLoading ? <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" /> : 'Sign in'}
                    </button>
                </form>
            </div>

            <div className="mt-8 text-[var(--text-secondary)]/50 text-sm">
                &copy; {new Date().getFullYear()} Inzyts Platform. All rights reserved.
            </div>
        </div>
    );
};

export default LoginPage;
