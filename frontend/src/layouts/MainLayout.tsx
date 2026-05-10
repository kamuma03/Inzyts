
import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useJobContext } from '../context/JobContext';
import { Sidebar } from '../components/Sidebar';
import { Toast } from '../components/Toast';
import { ProgressPill } from '../components/state';
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

    return (
        <div className="h-screen flex flex-col font-sans overflow-hidden bg-[var(--surface-0)]">
            {/* Toast Container */}
            <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2">
                {toasts.map(toast => (
                    <Toast key={toast.id} {...toast} />
                ))}
            </div>

            <header className="shrink-0 flex items-center justify-between px-6 py-2 border-b border-[var(--rule)] bg-[var(--surface-0)] z-10 max-md:px-4 max-md:py-1.5 max-md:flex-wrap max-md:gap-2">
                <div className="flex items-center gap-3">
                    <img src="/Inzyts_icon.png" alt="Inzyts Logo" className="w-8 h-8" />
                    <div className="mr-6 max-md:mr-2">
                        <h1 className="m-0 text-[1.4rem] font-bold text-[var(--text-primary)] leading-tight max-md:text-[1.1rem]">Inzyts</h1>
                        <p className="m-0 text-[0.75rem] text-[var(--text-secondary)] max-md:text-[0.7rem]">Analyze. Predict. Discover.</p>
                    </div>

                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => navigate('/templates')}
                            className="text-xs px-3 py-1.5 bg-[var(--surface-2)] hover:bg-[var(--rule-strong)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--rule)] rounded-md transition-colors"
                        >
                            Templates
                        </button>
                        {isAdmin() && (
                            <>
                                <button
                                    onClick={() => navigate('/admin/users')}
                                    className="text-xs px-3 py-1.5 bg-[var(--surface-2)] hover:bg-[var(--rule-strong)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--rule)] rounded-md transition-colors"
                                >
                                    Users
                                </button>
                                <button
                                    onClick={() => navigate('/admin/audit')}
                                    className="text-xs px-3 py-1.5 bg-[var(--surface-2)] hover:bg-[var(--rule-strong)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--rule)] rounded-md transition-colors"
                                >
                                    Audit log
                                </button>
                            </>
                        )}
                    </div>
                    <ProgressPill
                        intent={isConnected ? 'ok' : 'bad'}
                        caption={isConnected ? 'Connected' : 'Disconnected'}
                    />
                    <span className="text-[var(--text-secondary)] text-xs">
                        {getStoredUsername()} <span className="text-[var(--text-dim)]">({getStoredRole()})</span>
                    </span>
                    <button
                        onClick={() => {
                            sessionStorage.removeItem('inzyts_jwt_token');
                            sessionStorage.removeItem('inzyts_user_role');
                            sessionStorage.removeItem('inzyts_username');
                            navigate('/login');
                        }}
                        className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors duration-200"
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

                {/* Center Content (Outlet) — full remaining width now that the
                    right rail is gone. The TopStrip already surfaces filename,
                    mode, and connection state, and the StatusBar carries
                    retries + shortcut hints. */}
                <div className="flex-1 flex flex-col min-h-0 min-w-0">
                    <Outlet />
                </div>
            </div>
        </div>
    );
};
