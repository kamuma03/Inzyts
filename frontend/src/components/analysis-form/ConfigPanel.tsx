import { useState, useCallback, useRef, type FC, type ChangeEvent, type DragEvent } from 'react';
import type { AnalysisRequest } from '../../api';
import { ModeSelector } from '../ModeSelector';
import { UploadCloud, FileText, X } from 'lucide-react';

interface ConfigPanelProps {
    dictPath: string;
    onDictFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
    onDictFileDrop?: (file: File) => void;
    targetCol: string;
    setTargetCol: (v: string) => void;
    excludeCols: string;
    setExcludeCols: (v: string) => void;
    mode: AnalysisRequest['mode'];
    setMode: (v: AnalysisRequest['mode']) => void;
    suggestedMode: AnalysisRequest['mode'] | null;
    suggestionExplanation: string | null;
    question: string;
    setQuestion: (v: string) => void;
    useCache: boolean;
    setUseCache: (v: boolean) => void;
    onDictClear?: () => void;
}

const DICT_EXTENSIONS = ['.csv', '.json', '.txt'];

export const ConfigPanel: FC<ConfigPanelProps> = ({
    dictPath, onDictFileChange, onDictFileDrop, targetCol, setTargetCol,
    excludeCols, setExcludeCols, mode, setMode,
    suggestedMode, suggestionExplanation, question, setQuestion,
    useCache, setUseCache, onDictClear,
}) => {
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        const droppedFiles = Array.from(e.dataTransfer.files);
        const validFile = droppedFiles.find(f =>
            DICT_EXTENSIONS.some(ext => f.name.toLowerCase().endsWith(ext))
        );

        if (validFile && onDictFileDrop) {
            onDictFileDrop(validFile);
        }
    }, [onDictFileDrop]);

    return (
        <>
            {/* Dataset Info + Target + Exclude — single row */}
            <div className="grid grid-cols-3 gap-4">
                <div>
                    <label className="block text-[0.8rem] mb-1.5 text-[var(--text-secondary)]">Dataset Info</label>
                    {dictPath ? (
                        <div className="flex items-center gap-2 py-2 px-2.5 bg-[rgba(0,0,0,0.2)] rounded border border-[var(--border-color)] h-[38px]">
                            <FileText size={14} className="text-[var(--bg-turquoise-surf)] shrink-0" />
                            <span className="text-[0.8rem] text-[var(--bg-turquoise-surf)] flex-1 truncate">
                                {dictPath.split('/').pop()}
                            </span>
                            {onDictClear && (
                                <button
                                    type="button"
                                    onClick={onDictClear}
                                    className="p-0 border-none bg-transparent cursor-pointer text-[var(--text-secondary)] hover:text-[#fc8181] transition-colors"
                                    aria-label="Remove dataset info"
                                >
                                    <X size={14} />
                                </button>
                            )}
                        </div>
                    ) : (
                        <div
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className={`border border-dashed rounded py-2 px-2.5 flex items-center gap-2 cursor-pointer transition-all duration-200 h-[38px] ${
                                isDragOver
                                    ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.08)]'
                                    : 'border-[var(--border-color)] bg-[rgba(0,0,0,0.1)]'
                            }`}
                        >
                            <UploadCloud
                                size={16}
                                className={`shrink-0 transition-colors duration-200 ${
                                    isDragOver ? 'text-[var(--bg-turquoise-surf)]' : 'text-[var(--text-secondary)]'
                                }`}
                            />
                            <span className={`text-[0.8rem] ${
                                isDragOver ? 'text-[var(--bg-turquoise-surf)]' : 'text-[var(--text-secondary)]'
                            }`}>
                                {isDragOver ? 'Drop here' : 'Drop or browse'}
                            </span>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".csv,.json,.txt"
                                onChange={onDictFileChange}
                                className="hidden"
                            />
                        </div>
                    )}
                </div>
                <div>
                    <label className="block text-[0.8rem] mb-1.5 text-[var(--text-secondary)]">Target Column</label>
                    <input
                        type="text"
                        value={targetCol}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setTargetCol(e.target.value)}
                        placeholder="e.g. Churn, Price"
                        className="w-full py-2 px-2.5 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[0.85rem] h-[38px]"
                    />
                </div>
                <div>
                    <label className="block text-[0.8rem] mb-1.5 text-[var(--text-secondary)]">Exclude Columns</label>
                    <input
                        type="text"
                        value={excludeCols}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setExcludeCols(e.target.value)}
                        placeholder="e.g. id, timestamp"
                        className="w-full py-2 px-2.5 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[0.85rem] h-[38px]"
                    />
                </div>
            </div>

            {/* Analysis Goal */}
            <div>
                <label className="block text-[0.8rem] mb-1.5 text-[var(--text-secondary)]">Analysis Goal</label>
                <ModeSelector
                    selectedMode={mode}
                    onSelect={setMode}
                    suggestedMode={suggestedMode}
                    suggestionExplanation={suggestionExplanation}
                />
            </div>

            {/* Question + Cache — side by side */}
            <div className="grid grid-cols-[1fr_auto] gap-4 items-end">
                <div>
                    <label className="block text-[0.8rem] mb-1.5 text-[var(--text-secondary)]">Analysis Question / Goal</label>
                    <textarea
                        value={question}
                        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setQuestion(e.target.value)}
                        placeholder="e.g. What factors correlate most strongly with the target?"
                        rows={3}
                        className="w-full py-2 px-2.5 rounded border border-[var(--border-color)] font-[inherit] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[0.85rem]"
                    />
                </div>
                <label className="flex items-center gap-2 cursor-pointer py-2 px-3 bg-[rgba(0,0,0,0.15)] rounded border border-[var(--border-color)] whitespace-nowrap h-fit">
                    <input
                        type="checkbox"
                        checked={useCache}
                        onChange={(e) => setUseCache(e.target.checked)}
                        className="w-4 h-4 accent-[var(--bg-turquoise-surf)] cursor-pointer"
                    />
                    <span className="text-[0.8rem] text-[var(--text-primary)]">Use cache</span>
                </label>
            </div>
        </>
    );
};
