
import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useJobContext } from '../context/JobContext';
import { Sidebar } from '../components/Sidebar';
import { ContextPanel } from '../components/ContextPanel';
import { Toast } from '../components/Toast';
import { isAdmin, getStoredUsername, getStoredRole } from '../api';

export const MainLayout: React.FC = () => {
    const navigate = useNavigate();
    const {
        jobs,
        activeJobId,
        isConnected,
        toasts,
        handleUpgradeJob,
        clearInitialFormState
    } = useJobContext();

    const selectedJob = jobs.find(j => j.id === activeJobId);

    // Navigation Handlers
    const handleSelectJob = (jobId: string) => {
        navigate(`/jobs/${jobId}`);
    };

    const handleNewAnalysis = () => {
        clearInitialFormState();
        navigate('/');
    };

    const onUpgradeJobWrapper = (job: any) => {
        handleUpgradeJob(job);
        navigate('/'); // Go to form
    };

    const handleShowTemplates = () => {
        navigate('/templates');
    };

    return (
        <div className="h-screen flex flex-col font-sans overflow-hidden bg-[var(--bg-deep-twilight)]">
            {/* Toast Container */}
            <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2">
                {toasts.map(toast => (
                    <Toast key={toast.id} {...toast} />
                ))}
            </div>

            <header className="shrink-0 flex items-center justify-between px-6 py-2 border-b border-[var(--border-color)] bg-[var(--bg-deep-twilight)] z-10 max-md:px-4 max-md:py-1.5 max-md:flex-wrap max-md:gap-2">
                <div className="flex items-center gap-3">
                    <img src="/Inzyts_icon.png" alt="Inzyts Logo" className="w-8 h-8" />
                    <div className="mr-6 max-md:mr-2">
                        <h1 className="m-0 text-[1.4rem] font-bold text-[var(--text-primary)] font-['Libre_Caslon_Display',serif] leading-tight max-md:text-[1.1rem]">Inzyts</h1>
                        <p className="m-0 text-[0.75rem] text-[var(--text-secondary)] max-md:text-[0.7rem]">Analyze. Predict. Discover.</p>
                    </div>

                </div>
                <div className="flex items-center gap-4">
                    {isAdmin() && (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => navigate('/admin/users')}
                                className="text-xs px-3 py-1.5 bg-slate-700/60 hover:bg-slate-600 text-slate-300 hover:text-white rounded-lg transition-colors"
                            >
                                Users
                            </button>
                            <button
                                onClick={() => navigate('/admin/audit')}
                                className="text-xs px-3 py-1.5 bg-slate-700/60 hover:bg-slate-600 text-slate-300 hover:text-white rounded-lg transition-colors"
                            >
                                Audit Log
                            </button>
                        </div>
                    )}
                    <div className={`px-4 py-2 rounded-[20px] text-[0.9rem] font-semibold ${
                        isConnected
                            ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-700/50'
                            : 'bg-red-900/30 text-red-400 border border-red-700/50'
                    }`}>
                        {isConnected ? '● Connected' : '○ Disconnected'}
                    </div>
                    <span className="text-slate-400 text-xs">
                        {getStoredUsername()} <span className="text-slate-600">({getStoredRole()})</span>
                    </span>
                    <button
                        onClick={() => {
                            sessionStorage.removeItem('inzyts_jwt_token');
                            sessionStorage.removeItem('inzyts_user_role');
                            sessionStorage.removeItem('inzyts_username');
                            navigate('/login');
                        }}
                        className="text-slate-400 hover:text-white transition-colors duration-200"
                        title="Sign Out"
                        aria-label="Sign out"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                    </button>
                </div>
            </header>

            {/* Main Flex Container */}
            <div className="flex-1 flex gap-6 p-6 min-h-0 max-md:p-3 max-md:gap-3">
                {/* Left Sidebar */}
                <div className="shrink-0 overflow-y-auto max-h-full hidden lg:block">
                    <Sidebar
                        jobs={jobs}
                        onSelectJob={handleSelectJob}
                        activeJobId={activeJobId}
                        onNewAnalysis={handleNewAnalysis}
                        onUpgradeJob={onUpgradeJobWrapper}
                    />
                </div>

                {/* Center Content (Outlet) */}
                <div className="flex-1 flex gap-6 min-h-0 min-w-0">
                    <div className="flex-1 flex flex-col min-h-0 min-w-0 pr-2">
                        <Outlet />
                    </div>
                </div>

                {/* Right Panel: Context */}
                <div className="shrink-0 overflow-y-auto max-h-full hidden lg:block">
                    <ContextPanel
                        selectedJob={selectedJob}
                        isConnected={isConnected}
                        onShowTemplates={handleShowTemplates}
                    />
                </div>
            </div>
        </div>
    );
};
