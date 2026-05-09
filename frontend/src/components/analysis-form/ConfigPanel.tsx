import { useState, useCallback, useRef, type FC, type ChangeEvent, type DragEvent } from 'react';
import type { AnalysisRequest } from '../../api';
import { ModeSelector } from '../ModeSelector';
import { UploadCloud, FileText, X, ChevronDown } from 'lucide-react';

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
    suggestionConfidence?: number | null;
    suggestionMatchedKeywords?: string[];
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
    suggestedMode, suggestionExplanation,
    suggestionConfidence, suggestionMatchedKeywords,
    question, setQuestion,
    useCache, setUseCache, onDictClear,
}) => {
    const [isDragOver, setIsDragOver] = useState(false);
    const [advancedOpen, setAdvancedOpen] = useState(false);
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
            {/* Hero question textarea — drives mode suggestion and target inference. */}
            <div>
                <label
                    htmlFor="analysis-question"
                    className="block text-[12px] mb-2 text-[var(--text-secondary)]"
                >
                    What do you want to know?
                </label>
                <textarea
                    id="analysis-question"
                    value={question}
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setQuestion(e.target.value)}
                    placeholder="e.g. Forecast next quarter sales and flag the product lines driving change"
                    rows={3}
                    className="w-full py-3 px-3 rounded border border-[var(--rule)] font-[inherit] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[18px] leading-[1.4] [text-wrap:pretty]"
                />
            </div>

            {/* Mode selector — suggestion pill + WHY card render directly under
                the question that drives them. */}
            <div>
                <ModeSelector
                    selectedMode={mode}
                    onSelect={setMode}
                    suggestedMode={suggestedMode}
                    suggestionExplanation={suggestionExplanation}
                    suggestionConfidence={suggestionConfidence}
                    suggestionMatchedKeywords={suggestionMatchedKeywords}
                />
            </div>

            {/* Advanced disclosure — target col, exclude cols, dict path, cache. */}
            <details
                open={advancedOpen}
                onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
                className="border border-[var(--rule)] rounded-md bg-[rgba(0,0,0,0.15)]"
            >
                <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer text-[12px] font-medium text-[var(--text-secondary)] list-none [&::-webkit-details-marker]:hidden">
                    <ChevronDown
                        size={14}
                        className={`transition-transform ${advancedOpen ? 'rotate-0' : '-rotate-90'}`}
                    />
                    Advanced
                </summary>
                <div className="px-3 pb-3 pt-1 flex flex-col gap-3">
                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="block text-[12px] mb-1.5 text-[var(--text-secondary)]">Dataset info</label>
                            {dictPath ? (
                                <div className="flex items-center gap-2 py-2 px-2.5 bg-[rgba(0,0,0,0.2)] rounded border border-[var(--rule)] h-[38px]">
                                    <FileText size={14} className="text-[var(--accent)] shrink-0" />
                                    <span className="text-[12px] text-[var(--accent)] flex-1 truncate">
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
                                            ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                                            : 'border-[var(--rule)] bg-[rgba(0,0,0,0.1)]'
                                    }`}
                                >
                                    <UploadCloud
                                        size={16}
                                        className={`shrink-0 transition-colors duration-200 ${
                                            isDragOver ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]'
                                        }`}
                                    />
                                    <span className={`text-[12px] ${
                                        isDragOver ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]'
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
                            <label className="block text-[12px] mb-1.5 text-[var(--text-secondary)]">Target column</label>
                            <input
                                type="text"
                                value={targetCol}
                                onChange={(e: ChangeEvent<HTMLInputElement>) => setTargetCol(e.target.value)}
                                placeholder="e.g. Churn, Price"
                                className="w-full py-2 px-2.5 rounded border border-[var(--rule)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[12px] h-[38px]"
                            />
                        </div>
                        <div>
                            <label className="block text-[12px] mb-1.5 text-[var(--text-secondary)]">Exclude columns</label>
                            <input
                                type="text"
                                value={excludeCols}
                                onChange={(e: ChangeEvent<HTMLInputElement>) => setExcludeCols(e.target.value)}
                                placeholder="e.g. id, timestamp"
                                className="w-full py-2 px-2.5 rounded border border-[var(--rule)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[12px] h-[38px]"
                            />
                        </div>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer text-[12px] text-[var(--text-primary)]">
                        <input
                            type="checkbox"
                            checked={useCache}
                            onChange={(e) => setUseCache(e.target.checked)}
                            className="w-4 h-4 accent-[var(--accent)] cursor-pointer"
                        />
                        Use cache
                    </label>
                </div>
            </details>
        </>
    );
};
