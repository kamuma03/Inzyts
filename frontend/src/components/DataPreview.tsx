import React from 'react';
import { AnalysisAPI } from '../api';
import { FileText } from 'lucide-react';
import { useFetchData } from '../hooks/useFetchData';

interface DataPreviewProps {
    filePath: string | null;
}

interface PreviewData {
    filename: string;
    columns: string[];
    rows: any[];
    total_rows: number;
}

export const DataPreview: React.FC<DataPreviewProps> = ({ filePath }) => {
    const { data: preview, loading, error } = useFetchData<PreviewData>(
        () => AnalysisAPI.getFilePreview(filePath!),
        [filePath],
        { enabled: !!filePath }
    );

    if (!filePath) return null;
    if (loading) return <div className="p-4 italic text-[var(--text-secondary)]">Loading preview...</div>;
    if (error) return <div className="p-4 text-red-400">{error}</div>;
    if (!preview) return null;

    return (
        <div className="mt-4 border border-[var(--border-color)] rounded-lg overflow-hidden">
            <div className="px-3 py-2.5 bg-[var(--bg-true-cobalt)] border-b border-[var(--border-color)] flex items-center gap-2 font-semibold text-[var(--text-primary)]">
                <FileText size={16} /> Data Preview: {preview.filename}
            </div>
            <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[0.85rem]">
                    <thead>
                        <tr className="bg-black/20">
                            {preview.columns.map((col) => (
                                <th key={col} className="p-2 border-b border-[var(--border-color)] text-left text-[var(--text-secondary)]">{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {preview.rows.map((row, i) => (
                            <tr key={i} className="border-b border-white/10">
                                {preview.columns.map((col) => (
                                    <td key={col} className="p-2 text-[var(--text-primary)]">{String(row[col] ?? '')}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="p-2 text-[0.8rem] text-[var(--text-secondary)] bg-[var(--bg-true-cobalt)] border-t border-[var(--border-color)]">
                Showing {preview.rows.length} of {preview.total_rows.toLocaleString()} rows
            </div>
        </div>
    );
};
