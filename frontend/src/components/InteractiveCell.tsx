import React, { useState, useRef, useEffect } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Sparkles, Check, AlertTriangle } from 'lucide-react';
import { formatMarkdown } from '../utils/formatMarkdown';
import { CellOutput, NotebookCellData } from '../types/notebook';

interface InteractiveCellProps {
    cell: NotebookCellData;
    index: number;
    jobId: string;
    onCellUpdate: (index: number, newCode: string, outputs: CellOutput[]) => void;
}

export const InteractiveCell: React.FC<InteractiveCellProps> = ({ cell, index, jobId, onCellUpdate }) => {
    const [instruction, setInstruction] = useState('');
    const [isEditing, setIsEditing] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [editStatus, setEditStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);
    const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

    // Clear all pending timeouts on unmount to prevent state updates on unmounted component
    useEffect(() => {
        return () => {
            timersRef.current.forEach(clearTimeout);
            timersRef.current = [];
        };
    }, []);

    const safeTimeout = (fn: () => void, ms: number) => {
        const id = setTimeout(fn, ms);
        timersRef.current.push(id);
        return id;
    };

    const handleEdit = async () => {
        if (!instruction.trim() || cell.cell_type !== 'code' || editStatus === 'loading') return;

        setEditStatus('loading');
        setErrorMsg('');

        try {
            const result = await AnalysisAPI.editCell(jobId, index, cell.source, instruction.trim());

            if (result.success) {
                // Build new outputs
                const newOutputs: CellOutput[] = [];
                if (result.output) {
                    newOutputs.push({ output_type: 'stream', text: result.output });
                }
                if (result.images && result.images.length > 0) {
                    result.images.forEach((img: string) => {
                        newOutputs.push({ output_type: 'display_data', data: { 'image/png': img } });
                    });
                }

                onCellUpdate(index, result.new_code, newOutputs);
                setEditStatus('success');
                setInstruction('');
                safeTimeout(() => {
                    setEditStatus('idle');
                    setIsEditing(false);
                }, 2000);
            } else {
                setEditStatus('error');
                setErrorMsg(result.error || 'Edit failed');
                safeTimeout(() => setEditStatus('idle'), 4000);
            }
        } catch (err) {
            setEditStatus('error');
            setErrorMsg('Network error');
            safeTimeout(() => setEditStatus('idle'), 4000);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleEdit();
        }
        if (e.key === 'Escape') {
            setIsEditing(false);
            setInstruction('');
        }
    };

    const isCode = cell.cell_type === 'code';

    return (
        <div
            className="flex gap-0 border border-transparent rounded-md transition-all duration-200 hover:border-[var(--border-color)] hover:shadow-[0_0_0_1px_rgba(76,201,240,0.1)]"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => { if (!isEditing) setIsHovered(false); }}
        >
            {/* Cell type indicator */}
            <div className="shrink-0 w-[60px] py-2 px-1 flex justify-end items-start">
                <span className="text-[0.7rem] font-mono text-[var(--text-secondary)] opacity-70">
                    {isCode ? `In [${index}]` : 'Md'}
                </span>
            </div>

            {/* Cell content */}
            <div className="flex-1 min-w-0 py-2 px-3">
                {isCode ? (
                    <pre className="font-mono text-[0.85rem] leading-relaxed text-[#e6edf3] bg-[rgba(27,38,59,0.6)] px-4 py-3 rounded m-0 whitespace-pre-wrap break-words overflow-x-auto">{cell.source}</pre>
                ) : (
                    <div
                        className="text-[var(--text-primary)] leading-[1.7] py-1 [&_h1]:text-[1.4rem] [&_h1]:my-2 [&_h1]:text-[var(--text-primary)] [&_h2]:text-[1.2rem] [&_h2]:my-1.5 [&_h2]:text-[var(--text-primary)] [&_h3]:text-base [&_h3]:my-1 [&_h3]:text-[var(--text-primary)] [&_code]:bg-[rgba(27,38,59,0.6)] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-sm [&_code]:text-[0.85em]"
                        dangerouslySetInnerHTML={{ __html: formatMarkdown(cell.source) }}
                    />
                )}

                {/* Outputs */}
                {cell.outputs.length > 0 && (
                    <div className="mt-2 border-t border-[rgba(65,90,119,0.3)] pt-2">
                        {cell.outputs.map((output, oi) => (
                            <div key={oi} className="mb-2">
                                {output.data?.['image/png'] && (
                                    <img
                                        src={`data:image/png;base64,${output.data['image/png']}`}
                                        alt={`Chart output ${oi}`}
                                        className="max-w-full rounded mt-1 border border-[rgba(65,90,119,0.3)]"
                                    />
                                )}
                                {output.text && (
                                    <pre className="font-mono text-[0.8rem] text-[var(--text-secondary)] bg-[rgba(13,27,42,0.5)] px-3 py-2 rounded m-0 whitespace-pre-wrap overflow-x-auto">{output.text}</pre>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* Edit bar — visible on hover for code cells */}
                {isCode && (isHovered || isEditing) && (
                    <div className="mt-2 animate-[slideIn_0.15s_ease-out]">
                        {!isEditing ? (
                            <button
                                className="inline-flex items-center gap-1.5 text-[0.78rem] text-[var(--bg-turquoise-surf)] bg-transparent border border-dashed border-[rgba(76,201,240,0.3)] rounded px-2.5 py-1 cursor-pointer transition-all duration-200 hover:bg-[rgba(76,201,240,0.08)] hover:border-[var(--bg-turquoise-surf)]"
                                onClick={() => {
                                    setIsEditing(true);
                                    setTimeout(() => inputRef.current?.focus(), 100);
                                }}
                            >
                                <Sparkles size={14} />
                                Tweak this cell
                            </button>
                        ) : (
                            <div className="flex items-center gap-2 bg-[rgba(27,38,59,0.8)] border border-[var(--bg-turquoise-surf)] rounded-md px-2.5 py-1.5">
                                <Sparkles size={14} className="text-[var(--bg-turquoise-surf)] shrink-0" />
                                <input
                                    ref={inputRef}
                                    type="text"
                                    className="flex-1 bg-transparent border-none outline-none text-[var(--text-primary)] text-[0.85rem] font-sans placeholder:text-[var(--text-secondary)] placeholder:opacity-60"
                                    placeholder={`e.g. "Make this a pie chart with a vibrant palette"`}
                                    value={instruction}
                                    onChange={(e) => setInstruction(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    disabled={editStatus === 'loading'}
                                />
                                {editStatus === 'loading' && (
                                    <Loader size={16} className="animate-spin text-[var(--bg-turquoise-surf)]" />
                                )}
                                {editStatus === 'success' && (
                                    <Check size={16} className="text-green-500" />
                                )}
                                {editStatus === 'error' && (
                                    <span className="flex items-center gap-1 text-[0.75rem] text-red-500 whitespace-nowrap">
                                        <AlertTriangle size={14} />
                                        {errorMsg}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
