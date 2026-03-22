import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
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
        <div className="min-h-screen bg-[var(--bg-deep-twilight)] flex flex-col items-center justify-center p-4">

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

            <div className="bg-[var(--bg-true-cobalt)]/80 backdrop-blur-md rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.3)] p-8 w-full max-w-[420px] border border-[var(--border-color)]/50">
                <form onSubmit={handleSubmit} className="space-y-6">
                    {error && (
                        <div className="p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm flex items-start gap-2">
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
                                className="w-full px-5 py-3.5 bg-[var(--bg-deep-twilight)]/50 border border-[var(--border-color)] rounded-xl text-white placeholder-[var(--text-secondary)]/50 focus:ring-2 focus:ring-[var(--bg-blue-green)]/50 focus:border-[var(--bg-blue-green)] outline-none transition-all"
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
                                className="w-full px-5 py-3.5 bg-[var(--bg-deep-twilight)]/50 border border-[var(--border-color)] rounded-xl text-white placeholder-[var(--text-secondary)]/50 focus:ring-2 focus:ring-[var(--bg-blue-green)]/50 focus:border-[var(--bg-blue-green)] outline-none transition-all"
                                placeholder="Enter password"
                                required
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full mt-2 bg-gradient-to-r from-[var(--bg-sky-aqua)] to-[var(--bg-blue-green)] hover:brightness-110 text-white font-semibold py-4 px-6 rounded-xl transition-all duration-200 transform hover:-translate-y-0.5 shadow-lg shadow-[var(--bg-sky-aqua)]/25 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex justify-center items-center"
                    >
                        {isLoading ? (
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : 'Sign In'}
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
