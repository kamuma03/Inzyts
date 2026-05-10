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

    // Modal a11y — Esc dismisses, focus the cancel button on open.
    const cancelButtonRef = React.useRef<HTMLButtonElement>(null);
    useEffect(() => {
        if (!confirmState?.isOpen) return;
        cancelButtonRef.current?.focus();
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setConfirmState(null);
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [confirmState?.isOpen]);

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
            await fetchTemplates();
            addToast('Template uploaded successfully', 'success');
        } catch (err: any) {
            addToast('Failed to upload template: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setUploading(false);
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
        setConfirmState(null);
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
            <div className="h-full flex flex-col items-center justify-center text-[var(--text-secondary)] gap-4">
                <Loader className="animate-spin text-[var(--accent)]" size={32} />
                <p>Loading templates...</p>
            </div>
        );
    }

    return (
        <div className="h-full p-6 bg-[var(--surface-1)] border border-[var(--rule)] rounded-lg flex flex-col overflow-hidden relative">
            {/* Toasts */}
            <div className="absolute top-4 right-4 z-50 flex flex-col gap-2">
                {toasts.map(t => (
                    <Toast key={t.id} id={t.id} message={t.message} type={t.type} onClose={removeToast} />
                ))}
            </div>

            {/* Confirmation Modal */}
            {confirmState && confirmState.isOpen && (
                <div
                    className="absolute inset-0 z-40 bg-black/60 flex items-center justify-center"
                    onClick={() => setConfirmState(null)}
                >
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="confirm-title"
                        onClick={(e) => e.stopPropagation()}
                        className="bg-[var(--surface-1)] border border-[var(--rule)] rounded-lg p-6 max-w-[400px] w-full shadow-[0_20px_25px_-5px_rgba(0,0,0,0.4)]"
                    >
                        <h3 id="confirm-title" className="mt-0 text-[var(--text-primary)] text-[1.1rem] mb-2">Confirm action</h3>
                        <p className="text-[var(--text-secondary)] mb-6">{confirmState.message}</p>
                        <div className="flex gap-3 justify-end">
                            <button
                                ref={cancelButtonRef}
                                onClick={() => setConfirmState(null)}
                                className="px-4 py-2 rounded-md cursor-pointer bg-transparent border border-[var(--rule)] text-[var(--text-secondary)] hover:bg-white/[0.04] hover:text-[var(--text-primary)] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmState.onConfirm}
                                className="px-4 py-2 rounded-md cursor-pointer bg-[var(--bad)] text-[var(--bad-ink)] font-semibold hover:brightness-110 transition"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-4">
                    {onBack && (
                        <button
                            onClick={onBack}
                            className="p-2 bg-white/[0.04] border border-[var(--rule)] rounded-md text-[var(--text-secondary)] cursor-pointer transition-colors hover:bg-white/[0.08] hover:text-[var(--text-primary)]"
                            title="Back to Dashboard"
                            aria-label="Back to Dashboard"
                        >
                            <ArrowLeft size={20} />
                        </button>
                    )}
                    <div>
                        <h2 className="text-[1.4rem] font-semibold text-[var(--text-primary)] m-0 flex items-center gap-3">
                            Domain templates
                        </h2>
                        <p className="text-[var(--text-secondary)] mt-1 text-[13px]">
                            Manage detection patterns for industry-specific analysis.
                        </p>
                    </div>
                </div>

                <label className="flex items-center gap-2 px-4 py-2.5 bg-[var(--accent)] text-[var(--accent-ink)] rounded-md cursor-pointer font-semibold text-[14px] transition hover:brightness-110">
                    <Upload size={16} />
                    {uploading ? 'Uploading…' : 'Upload template'}
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
                <div className="mb-6 p-3 bg-[rgba(248,113,113,0.1)] border border-[rgba(248,113,113,0.3)] text-[var(--bad)] rounded-md text-[13px]">
                    {error}
                </div>
            )}

            {/* Grid Content */}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4 overflow-y-auto pb-4 flex-1">
                {templates.map((template) => (
                    <div
                        key={template.domain_name}
                        className="bg-[var(--surface-2)] border border-[var(--rule)] rounded-lg p-5 transition-colors flex flex-col relative hover:border-[var(--rule-strong)]"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-md bg-[var(--accent-soft)] flex items-center justify-center text-[var(--accent)]">
                                    <Layers size={20} />
                                </div>
                                <h3 className="text-[1rem] font-semibold text-[var(--text-primary)] m-0">
                                    {template.domain_name}
                                </h3>
                            </div>
                            <button
                                onClick={() => handleDeleteClick(template.domain_name)}
                                className="bg-transparent border-none text-[var(--text-secondary)] p-1.5 rounded-md cursor-pointer transition-colors hover:bg-[rgba(248,113,113,0.1)] hover:text-[var(--bad)]"
                                title="Delete Template"
                                aria-label={`Delete ${template.domain_name} template`}
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>

                        <p className="text-[var(--text-secondary)] text-[13px] leading-normal flex-1 mb-4 [text-wrap:pretty]">
                            {template.description}
                        </p>

                        <div className="flex flex-col gap-3">
                            <div>
                                <h4 className="text-[11px] font-semibold text-[var(--text-dim)] uppercase tracking-[0.04em] mb-2">Concepts</h4>
                                <div className="flex flex-wrap gap-1.5">
                                    {template.concepts.slice(0, 4).map(c => (
                                        <span key={c.name} className="px-2 py-0.5 bg-white/[0.04] rounded text-[12px] text-[var(--text-primary)] border border-[var(--rule)]">
                                            {c.name}
                                        </span>
                                    ))}
                                    {template.concepts.length > 4 && (
                                        <span className="px-2 py-0.5 text-[12px] text-[var(--text-dim)]">
                                            +{template.concepts.length - 4} more
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}

                {templates.length === 0 && !loading && (
                    <div className="col-span-full p-12 text-center bg-white/[0.02] rounded-lg border border-dashed border-[var(--rule)] text-[var(--text-secondary)] flex flex-col items-center gap-2">
                        <FileJson size={40} className="opacity-30" />
                        <p className="text-[14px] font-medium text-[var(--text-primary)] m-0">No templates yet</p>
                        <p className="text-[12px] opacity-70 m-0">Upload a JSON template to enhance your analysis capabilities.</p>
                    </div>
                )}
            </div>

            <div className="mt-auto pt-4 border-t border-[var(--rule)] flex items-start gap-3">
                <Info size={16} className="text-[var(--accent)] shrink-0 mt-0.5" />
                <p className="text-[12px] text-[var(--text-secondary)] leading-normal m-0">
                    Templates power the <strong className="text-[var(--text-primary)]">Data Profiler</strong> by automatically identifying domain-specific columns (like "Patient ID" for Healthcare). This allows the <strong className="text-[var(--text-primary)]">Strategy Agent</strong> to suggest highly relevant KPIs and deep-dive analyses tailored to your specific industry.
                </p>
            </div>
        </div>
    );
};
