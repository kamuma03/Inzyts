import { useCallback, useRef, type FC, type ChangeEvent } from 'react';
import type { AnalysisRequest } from '../../api';
import { ModeSelector } from '../ModeSelector';
import { UploadCloud, FileText, X, ChevronRight } from 'lucide-react';
import { useDragDrop } from '../../hooks/useDragDrop';

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
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDictFiles = useCallback((files: File[]) => {
        const validFile = files.find(f =>
            DICT_EXTENSIONS.some(ext => f.name.toLowerCase().endsWith(ext))
        );
        if (validFile && onDictFileDrop) onDictFileDrop(validFile);
    }, [onDictFileDrop]);

    const { isDragOver, onDragOver: handleDragOver, onDragLeave: handleDragLeave, onDrop: handleDrop } =
        useDragDrop(handleDictFiles);

    return (
        <>
            {/* Hero question textarea — autofocused on step 2 entry, the largest
                input on the page, and the input that drives mode suggestion. */}
            <div>
                <label
                    htmlFor="analysis-question"
                    className="block text-[14px] mb-2 text-[var(--text-secondary)]"
                >
                    What do you want to know?
                </label>
                <textarea
                    id="analysis-question"
                    value={question}
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setQuestion(e.target.value)}
                    placeholder="e.g. Forecast next quarter's revenue and flag the product lines driving change"
                    rows={3}
                    autoFocus
                    className="w-full py-3 px-3 rounded-md border border-[var(--rule)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[16px] leading-[1.4] [text-wrap:pretty] focus:border-[var(--accent)] outline-none transition-colors"
                />
            </div>

            {/* Mode selector renders directly under the input that drives it. */}
            <div>
                <label className="block text-[12px] mb-1.5 text-[var(--text-secondary)]">
                    Analysis goal
                </label>
                <ModeSelector
                    selectedMode={mode}
                    onSelect={setMode}
                    suggestedMode={suggestedMode}
                    suggestionExplanation={suggestionExplanation}
                    suggestionConfidence={suggestionConfidence}
                    suggestionMatchedKeywords={suggestionMatchedKeywords}
                />
            </div>

            {/* Advanced — collapsed by default; ~80% of runs use defaults. */}
            <details className="group rounded-md border border-[var(--rule)] bg-[rgba(0,0,0,0.15)]">
                <summary className="cursor-pointer px-3 py-2 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-2 list-none [&::-webkit-details-marker]:hidden transition-colors">
                    <ChevronRight
                        size={14}
                        className="group-open:rotate-90 transition-transform"
                    />
                    <span>Advanced — target column, exclude columns, dictionary, cache</span>
                </summary>

                <div className="px-3 pb-3 pt-1 grid grid-cols-3 gap-4">
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
                            className="w-full py-2 px-2.5 rounded border border-[var(--rule)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[13px] h-[38px]"
                        />
                    </div>
                    <div>
                        <label className="block text-[12px] mb-1.5 text-[var(--text-secondary)]">Exclude columns</label>
                        <input
                            type="text"
                            value={excludeCols}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setExcludeCols(e.target.value)}
                            placeholder="e.g. id, timestamp"
                            className="w-full py-2 px-2.5 rounded border border-[var(--rule)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[13px] h-[38px]"
                        />
                    </div>
                </div>

                <div className="px-3 pb-3 border-t border-[var(--rule)] mt-1 pt-3">
                    <label className="flex items-center gap-2 cursor-pointer text-[12px] text-[var(--text-primary)]">
                        <input
                            type="checkbox"
                            checked={useCache}
                            onChange={(e) => setUseCache(e.target.checked)}
                            className="w-4 h-4 accent-[var(--accent)] cursor-pointer"
                        />
                        Use cached profile if available
                    </label>
                </div>
            </details>
        </>
    );
};
