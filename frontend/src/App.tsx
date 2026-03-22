
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { JobProvider } from './context/JobContext';
import { MainLayout } from './layouts/MainLayout';
import { NewAnalysisPage } from './pages/NewAnalysisPage';
import { JobDetailsPage } from './pages/JobDetailsPage';
import { TemplatesPage } from './pages/TemplatesPage';
import LoginPage from './pages/LoginPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminAuditPage from './pages/AdminAuditPage';
import ErrorBoundary from './components/ErrorBoundary';
import { isAdmin } from './api';

const ProtectedRoute = () => {
    const token = sessionStorage.getItem('inzyts_jwt_token');
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    return <Outlet />;
};

const AdminRoute = () => {
    const token = sessionStorage.getItem('inzyts_jwt_token');
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    if (!isAdmin()) {
        return <Navigate to="/" replace />;
    }
    return <Outlet />;
};

function App() {
    return (
        <ErrorBoundary>
            <JobProvider>
                <BrowserRouter>
                    <Routes>
                        <Route path="/login" element={<LoginPage />} />
                        <Route element={<ProtectedRoute />}>
                            <Route element={<MainLayout />}>
                                <Route path="/" element={<NewAnalysisPage />} />
                                <Route path="/jobs/:jobId" element={<JobDetailsPage />} />
                                <Route path="/templates" element={<TemplatesPage />} />
                            </Route>
                        </Route>
                        <Route element={<AdminRoute />}>
                            <Route element={<MainLayout />}>
                                <Route path="/admin/users" element={<AdminUsersPage />} />
                                <Route path="/admin/audit" element={<AdminAuditPage />} />
                            </Route>
                        </Route>
                        {/* Fallback */}
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                </BrowserRouter>
            </JobProvider>
        </ErrorBoundary>
    )
}

export default App

