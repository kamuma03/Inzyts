import React, { useState, useEffect } from 'react';
import { AnalysisAPI, DomainTemplate } from '../api';
import { Toast } from './Toast';
import { Trash2, Upload, FileJson, Info, ArrowLeft, Loader, Layers } from 'lucide-react';

interface TemplateManagerProps {
    onBack?: () => void;
}

export const TemplateManager: React.FC<TemplateManagerProps> = ({ onBack }) => {
    const [templates, setTemplates] = useState<DomainTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [uploading, setUploading] = useState(false);

    // State for UI interactions
    const [toasts, setToasts] = useState<{ id: string, message: string, type: 'success' | 'error' | 'info' | 'warning' }[]>([]);
    const [confirmState, setConfirmState] = useState<{ isOpen: boolean, message: string, onConfirm: () => void } | null>(null);

    const addToast = (message: string, type: 'success' | 'error' | 'info' | 'warning' = 'info') => {
        const id = Math.random().toString(36).substr(2, 9);
        setToasts(prev => [...prev, { id, message, type }]);
        setTimeout(() => removeToast(id), 5000);
    };

    const removeToast = (id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    };

    const fetchTemplates = async () => {
        try {
            setLoading(true);
            const data = await AnalysisAPI.getTemplates();
            setTemplates(data);
            setError(null);
        } catch (err: any) {
            setError(err.message || 'Failed to load templates');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTemplates();
    }, []);

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
            addToast('Please upload a JSON file.', 'warning');
            return;
        }

        try {
            setUploading(true);
            await AnalysisAPI.uploadTemplate(file);
            await fetchTemplates(); // Refresh list
            addToast('Template uploaded successfully', 'success');
        } catch (err: any) {
            addToast('Failed to upload template: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setUploading(false);
            // Reset input
            event.target.value = '';
        }
    };

    const handleDeleteClick = (domainName: string) => {
        setConfirmState({
            isOpen: true,
            message: `Are you sure you want to delete the ${domainName} template?`,
            onConfirm: () => deleteTemplate(domainName)
        });
    };

    const deleteTemplate = async (domainName: string) => {
        setConfirmState(null); // Close modal
        try {
            await AnalysisAPI.deleteTemplate(domainName);
            await fetchTemplates();
            addToast(`Template ${domainName} deleted`, 'success');
        } catch (err: any) {
            addToast('Failed to delete template: ' + err.message, 'error');
        }
    };

    if (loading && templates.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-4">
                <Loader className="animate-spin text-blue-500" size={32} />
                <p>Loading templates...</p>
            </div>
        );
    }

    return (
        <div className="h-full p-8 bg-gradient-to-br from-[rgba(20,30,48,0.6)] to-[rgba(36,59,85,0.4)] backdrop-blur-[10px] rounded-2xl border border-white/[0.08] flex flex-col overflow-hidden relative">
            {/* Toasts */}
            <div className="absolute top-4 right-4 z-50 flex flex-col gap-2">
                {toasts.map(t => (
                    <Toast key={t.id} id={t.id} message={t.message} type={t.type} onClose={removeToast} />
                ))}
            </div>

            {/* Confirmation Modal */}
            {confirmState && confirmState.isOpen && (
                <div className="absolute inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center">
                    <div className="bg-[#1a202c] border border-white/10 rounded-xl p-8 max-w-[400px] w-full shadow-[0_20px_25px_-5px_rgba(0,0,0,0.1),0_10px_10px_-5px_rgba(0,0,0,0.04)]">
                        <h3 className="mt-0 text-white text-[1.2rem]">Confirm Action</h3>
                        <p className="text-gray-400 mb-6">{confirmState.message}</p>
                        <div className="flex gap-4 justify-end">
                            <button
                                onClick={() => setConfirmState(null)}
                                className="px-4 py-2 rounded-md cursor-pointer bg-transparent border border-gray-600 text-gray-400 hover:bg-gray-700 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmState.onConfirm}
                                className="px-4 py-2 rounded-md cursor-pointer bg-red-600 border-none text-white font-semibold hover:bg-red-700 transition-colors"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="flex justify-between items-center mb-8">
                <div className="flex items-center gap-4">
                    {onBack && (
                        <button
                            onClick={onBack}
                            className="p-2 bg-white/5 border border-white/10 rounded-xl text-[var(--text-secondary)] cursor-pointer transition-all duration-200 hover:bg-white/10 hover:text-white"
                            title="Back to Dashboard"
                        >
                            <ArrowLeft size={20} />
                        </button>
                    )}
                    <div>
                        <h2 className="text-[1.8rem] font-bold bg-gradient-to-r from-[#4cc9f0] to-[#4361ee] bg-clip-text text-transparent m-0 flex items-center gap-3">
                            Domain Templates
                        </h2>
                        <p className="text-[var(--text-secondary)] mt-1 text-[0.95rem]">
                            Manage detection patterns for industry-specific analysis.
                        </p>
                    </div>
                </div>

                <label className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-[#4361ee] to-[#4cc9f0] shadow-[0_4px_15px_rgba(67,97,238,0.3)] text-white rounded-xl cursor-pointer font-semibold text-[0.9rem] transition-transform duration-200 border-none hover:-translate-y-0.5">
                    <Upload size={18} />
                    {uploading ? 'Uploading...' : 'Upload Template'}
                    <input
                        type="file"
                        accept=".json"
                        onChange={handleFileUpload}
                        disabled={uploading}
                        className="hidden"
                    />
                </label>
            </div>

            {error && (
                <div className="mb-6 p-4 bg-red-600/10 border border-red-600/20 text-red-200 rounded-lg text-[0.9rem]">
                    {error}
                </div>
            )}

            {/* Grid Content */}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-6 overflow-y-auto pb-8 flex-1">
                {templates.map((template) => (
                    <div
                        key={template.domain_name}
                        className="bg-[rgba(30,30,40,0.6)] border border-white/5 rounded-2xl p-6 transition-all duration-300 flex flex-col relative shadow-[0_4px_20px_rgba(0,0,0,0.1)] hover:-translate-y-1 hover:shadow-[0_12px_24px_rgba(0,0,0,0.2)] hover:border-[rgba(67,97,238,0.3)]"
                    >
                        <div className="flex justify-between items-start mb-4">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-[10px] bg-[rgba(67,97,238,0.15)] flex items-center justify-center text-[#4cc9f0]">
                                    <Layers size={22} />
                                </div>
                                <h3 className="text-[1.1rem] font-semibold text-[var(--text-primary)] m-0">
                                    {template.domain_name}
                                </h3>
                            </div>
                            <button
                                onClick={() => handleDeleteClick(template.domain_name)}
                                className="bg-white/[0.03] border-none text-[var(--text-secondary)] p-1.5 rounded-md cursor-pointer transition-all duration-200 hover:bg-red-600/15 hover:text-red-200"
                                title="Delete Template"
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>

                        <p className="text-[var(--text-secondary)] text-[0.9rem] leading-normal flex-1 mb-6">
                            {template.description}
                        </p>

                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-[0.75rem] font-bold text-[#4cc9f0] uppercase tracking-wider mb-2">Concepts</h4>
                                <div className="flex flex-wrap gap-2">
                                    {template.concepts.slice(0, 4).map(c => (
                                        <span key={c.name} className="px-2.5 py-1 bg-white/5 rounded-md text-[0.8rem] text-slate-200 border border-white/5">
                                            {c.name}
                                        </span>
                                    ))}
                                    {template.concepts.length > 4 && (
                                        <span className="px-2 py-1 text-[0.8rem] text-[var(--text-secondary)] opacity-70">
                                            +{template.concepts.length - 4} more
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}

                {templates.length === 0 && !loading && (
                    <div className="col-span-full p-16 text-center bg-white/[0.02] rounded-2xl border-2 border-dashed border-white/10 text-[var(--text-secondary)]">
                        <FileJson size={48} className="opacity-20 mb-4" />
                        <p className="text-[1.1rem] font-medium">No templates found</p>
                        <p className="text-[0.9rem] opacity-70 mt-2">Upload a JSON template to enhance your analysis capabilities.</p>
                    </div>
                )}
            </div>

            <div className="mt-auto pt-6 border-t border-white/[0.08] flex items-start gap-3">
                <Info size={18} className="text-[#4cc9f0] shrink-0 mt-0.5" />
                <p className="text-[0.85rem] text-[var(--text-secondary)] leading-normal m-0">
                    Templates power the <strong>Data Profiler</strong> by automatically identifying domain-specific columns (like "Patient ID" for Healthcare). This allows the <strong>Strategy Agent</strong> to suggest highly relevant KPIs and deep-dive analyses tailored to your specific industry.
                </p>
            </div>
        </div>
    );
};
