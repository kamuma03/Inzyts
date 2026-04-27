import { FC, useState, useCallback, useRef, useEffect, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles, BarChart2, TrendingUp, GitCompare, Activity, PieChart, Layers, Info, Wand2 } from 'lucide-react';
import { AnalysisRequest } from '../api';

export const ANALYSIS_MODES: {
    id: AnalysisRequest['mode'];
    label: string;
    desc: string;
    detailedDesc: string;
    icon: any;
}[] = [
    {
        id: 'exploratory',
        label: 'Exploratory',
        desc: 'Understand what you have',
        detailedDesc: 'Performs comprehensive data profiling including missing values, distributions, correlations, and outlier detection. Best for initial data understanding when you don\'t have a specific hypothesis. Produces a detailed profile notebook without modeling.',
        icon: Sparkles
    },
    {
        id: 'predictive',
        label: 'Predictive',
        desc: 'Train a model for a target',
        detailedDesc: 'Builds and evaluates machine learning models to predict a specified target column. Automatically selects between regression and classification based on the target type. Includes feature importance, cross-validation, and model comparison.',
        icon: BarChart2
    },
    {
        id: 'forecasting',
        label: 'Forecasting',
        desc: 'Project values forward in time',
        detailedDesc: 'Analyzes temporal patterns using time-series models (Prophet, ARIMA, exponential smoothing). Requires data with a datetime column. Generates future predictions with confidence intervals and trend/seasonality decomposition.',
        icon: TrendingUp
    },
    {
        id: 'comparative',
        label: 'Comparative',
        desc: 'Test if groups differ',
        detailedDesc: 'Runs statistical tests to compare two or more groups in your data. Supports A/B testing, hypothesis testing, and effect size estimation. Ideal for experiment analysis, treatment vs control comparisons, or cohort analysis.',
        icon: GitCompare
    },
    {
        id: 'diagnostic',
        label: 'Diagnostic',
        desc: 'Find the root cause',
        detailedDesc: 'Investigates why specific outcomes or anomalies occurred using root cause analysis techniques. Identifies key drivers and contributing factors behind trends, drops, or spikes in your data.',
        icon: Activity
    },
    {
        id: 'segmentation',
        label: 'Segmentation',
        desc: 'Group rows into clusters',
        detailedDesc: 'Uses unsupervised clustering algorithms (K-Means, DBSCAN) to discover natural groupings in your data. Generates segment profiles with key characteristics and distributions for each cluster.',
        icon: PieChart
    },
    {
        id: 'dimensionality_reduction',
        label: 'Dimensionality',
        desc: 'Reduce feature space',
        detailedDesc: 'Reduces high-dimensional data to fewer components using PCA, t-SNE, or UMAP. Useful for visualization of complex datasets, feature compression, and understanding variance structure across many variables.',
        icon: Layers
    },
];

/** Small info icon with a tooltip rendered via portal to avoid overflow clipping. */
const InfoTooltip: FC<{ text: string }> = ({ text }) => {
    const [visible, setVisible] = useState(false);
    const [coords, setCoords] = useState({ top: 0, left: 0, showBelow: false });
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);

    const updatePosition = () => {
        if (!buttonRef.current) return;
        const rect = buttonRef.current.getBoundingClientRect();
        const showBelow = rect.top < 160;
        const tooltipWidth = 260;
        // Align right edge of tooltip with right edge of icon, clamp to viewport
        let left = rect.right - tooltipWidth;
        if (left < 8) left = 8;
        if (left + tooltipWidth > window.innerWidth - 8) left = window.innerWidth - tooltipWidth - 8;

        setCoords({
            top: showBelow ? rect.bottom + 8 : rect.top - 8,
            left,
            showBelow,
        });
    };

    const show = () => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        updatePosition();
        setVisible(true);
    };
    const hide = () => {
        timeoutRef.current = setTimeout(() => setVisible(false), 150);
    };
    const toggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (visible) {
            setVisible(false);
        } else {
            show();
        }
    };

    // Close on outside click or scroll
    useEffect(() => {
        if (!visible) return;
        const handleClose = (e: MouseEvent) => {
            if (
                buttonRef.current?.contains(e.target as Node) ||
                tooltipRef.current?.contains(e.target as Node)
            ) return;
            setVisible(false);
        };
        const handleScroll = () => setVisible(false);
        document.addEventListener('mousedown', handleClose);
        window.addEventListener('scroll', handleScroll, true);
        return () => {
            document.removeEventListener('mousedown', handleClose);
            window.removeEventListener('scroll', handleScroll, true);
        };
    }, [visible]);

    return (
        <>
            <button
                ref={buttonRef}
                type="button"
                onClick={toggle}
                onMouseEnter={show}
                onMouseLeave={hide}
                aria-label="More info"
                className="inline-flex items-center justify-center p-0 border-none bg-transparent cursor-pointer text-[var(--text-secondary)] opacity-50 hover:opacity-100 transition-opacity"
            >
                <Info size={14} />
            </button>
            {visible && createPortal(
                <div
                    ref={tooltipRef}
                    onMouseEnter={() => { if (timeoutRef.current) clearTimeout(timeoutRef.current); }}
                    onMouseLeave={hide}
                    style={{
                        position: 'fixed',
                        zIndex: 9999,
                        top: coords.showBelow ? coords.top : undefined,
                        bottom: coords.showBelow ? undefined : window.innerHeight - coords.top,
                        left: coords.left,
                        width: 260,
                    }}
                    className="p-3 text-[0.8rem] leading-[1.5] text-[var(--text-secondary)] bg-[var(--bg-deep-twilight)] border border-[var(--border-color)] rounded-lg shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
                >
                    {text}
                </div>,
                document.body,
            )}
        </>
    );
};

interface ModeSelectorProps {
    selectedMode: AnalysisRequest['mode'];
    onSelect: (mode: AnalysisRequest['mode']) => void;
    suggestedMode?: AnalysisRequest['mode'] | null;
    suggestionExplanation?: string | null;
    suggestionConfidence?: number | null;
    suggestionMatchedKeywords?: string[];
}

/** Highlight tokens in the explanation that look like keywords or column
 *  names — wraps backtick-quoted strings and double-quoted strings in mono
 *  styling so the WHY card reads like the design canvas. */
const renderExplanation = (text: string): React.ReactNode => {
    const parts: React.ReactNode[] = [];
    let i = 0;
    const re = /`([^`]+)`|"([^"]+)"/g;
    let match: RegExpExecArray | null;
    while ((match = re.exec(text)) !== null) {
        if (match.index > i) parts.push(text.slice(i, match.index));
        const token = match[1] ?? match[2] ?? '';
        parts.push(
            <code
                key={match.index}
                className="font-mono text-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.08)] px-1 py-px rounded text-[11px]"
            >
                {token}
            </code>,
        );
        i = match.index + match[0].length;
    }
    if (i < text.length) parts.push(text.slice(i));
    return parts;
};

const confidenceColor = (c: number | null | undefined): string => {
    if (c == null) return 'var(--text-dim)';
    if (c >= 0.7) return 'var(--status-good)';
    if (c >= 0.5) return 'var(--status-warn)';
    return 'var(--text-dim)';
};

const confidenceLabel = (c: number | null | undefined): string => {
    if (c == null) return 'unknown';
    if (c >= 0.7) return 'high confidence';
    if (c >= 0.5) return 'medium confidence';
    return 'low confidence';
};

export const ModeSelector: FC<ModeSelectorProps> = ({
    selectedMode, onSelect, suggestedMode, suggestionExplanation,
    suggestionConfidence, suggestionMatchedKeywords,
}) => {
    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
        const currentIndex = ANALYSIS_MODES.findIndex(m => m.id === selectedMode);
        let nextIndex = currentIndex;

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            nextIndex = (currentIndex + 1) % ANALYSIS_MODES.length;
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            nextIndex = (currentIndex - 1 + ANALYSIS_MODES.length) % ANALYSIS_MODES.length;
        } else if (e.key === 'Home') {
            e.preventDefault();
            nextIndex = 0;
        } else if (e.key === 'End') {
            e.preventDefault();
            nextIndex = ANALYSIS_MODES.length - 1;
        } else {
            return;
        }

        onSelect(ANALYSIS_MODES[nextIndex].id);
        const btn = document.getElementById(`mode-${ANALYSIS_MODES[nextIndex].id}`);
        btn?.focus();
    }, [selectedMode, onSelect]);

    const suggestedMeta = suggestedMode
        ? ANALYSIS_MODES.find((m) => m.id === suggestedMode)
        : null;
    const showSuggestion = !!suggestedMode && suggestedMode !== selectedMode;
    const [dismissedSuggestion, setDismissedSuggestion] = useState<string | null>(null);
    const dismissed = dismissedSuggestion === suggestedMode;

    return (
        <div>
            {/* Suggestion pill — appears only when the heuristic finds a confident match. */}
            {showSuggestion && !dismissed && suggestedMeta && (
                <div className="mb-3 flex items-center gap-2 px-3 py-1.5 rounded-full border border-[rgba(76,201,240,0.3)] bg-[rgba(76,201,240,0.04)] text-[12px] text-[var(--text-secondary)] w-fit">
                    <Wand2 size={12} className="text-[var(--bg-turquoise-surf)] shrink-0" />
                    <span>
                        Suggested:{' '}
                        <strong className="text-[var(--bg-turquoise-surf)] font-semibold">
                            {suggestedMeta.label}
                        </strong>
                    </span>
                    {suggestionMatchedKeywords && suggestionMatchedKeywords.length > 0 && (
                        <>
                            <span className="text-[var(--text-dim)]">·</span>
                            <span className="text-[var(--text-dim)]">
                                matched{' '}
                                <span className="text-[var(--text-secondary)] font-mono">
                                    {suggestionMatchedKeywords.map((k) => `"${k}"`).join(', ')}
                                </span>
                            </span>
                        </>
                    )}
                    <span
                        aria-label={confidenceLabel(suggestionConfidence)}
                        title={confidenceLabel(suggestionConfidence)}
                        className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ backgroundColor: confidenceColor(suggestionConfidence) }}
                    />
                    <button
                        type="button"
                        onClick={() => onSelect(suggestedMode!)}
                        className="ml-2 px-2.5 py-0.5 text-[12px] font-semibold bg-[var(--bg-turquoise-surf)] text-[var(--bg-deep-twilight)] border-none rounded cursor-pointer shrink-0"
                    >
                        Use {suggestedMeta.label.toLowerCase()}
                    </button>
                    <button
                        type="button"
                        onClick={() => setDismissedSuggestion(suggestedMode!)}
                        className="text-[11px] text-[var(--text-dim)] hover:text-[var(--text-secondary)] bg-transparent border-none cursor-pointer"
                    >
                        Dismiss
                    </button>
                </div>
            )}

            {/* WHY card — inline expanded explanation when a suggestion is active. */}
            {showSuggestion && !dismissed && suggestedMeta && suggestionExplanation && (
                <div className="mb-3 p-3 rounded-md border border-[var(--border-color)] bg-[var(--bg-surface-hi)]">
                    <div className="text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)] mb-1.5">
                        Why {suggestedMeta.label}?
                    </div>
                    <p className="m-0 text-[12px] leading-[1.5] text-[var(--text-secondary)]">
                        {renderExplanation(suggestionExplanation)}
                    </p>
                </div>
            )}

            {/* Section header for the grid */}
            <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                    All modes · click to override
                </span>
                <span
                    className="ml-auto font-mono text-[10px] text-[var(--text-dim)]"
                    aria-hidden="true"
                >
                    ↑ ↓ ← → to navigate
                </span>
            </div>

            <div
                role="radiogroup"
                aria-label="Analysis mode selection"
                onKeyDown={handleKeyDown}
                className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2"
            >
                {ANALYSIS_MODES.map((mode) => {
                    const isSelected = selectedMode === mode.id;
                    const isSuggested = suggestedMode === mode.id && !isSelected;
                    const Icon = mode.icon;
                    return (
                        <button
                            key={mode.id}
                            id={`mode-${mode.id}`}
                            onClick={() => onSelect(mode.id)}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            aria-label={`${mode.label} mode: ${mode.desc}`}
                            tabIndex={isSelected ? 0 : -1}
                            className={`group relative px-3 py-3 cursor-pointer flex flex-col gap-2 transition-all duration-150 w-full text-left appearance-none text-inherit rounded-md border ${
                                isSelected
                                    ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.06)]'
                                    : isSuggested
                                        ? 'border-[rgba(76,201,240,0.45)] bg-[var(--bg-surface-hi)]'
                                        : 'border-[var(--border-color)] bg-[var(--bg-surface-hi)] hover:border-[var(--text-dim)]'
                            }`}
                        >
                            {/* Top row: icon-in-box on the left, suggested marker on the right. */}
                            <div className="flex items-start justify-between">
                                <span
                                    className={`flex items-center justify-center w-7 h-7 rounded-md ${
                                        isSelected
                                            ? 'bg-[rgba(76,201,240,0.16)]'
                                            : 'bg-[rgba(0,0,0,0.25)]'
                                    }`}
                                >
                                    <Icon
                                        size={14}
                                        className={
                                            isSelected
                                                ? 'text-[var(--bg-turquoise-surf)]'
                                                : 'text-[var(--text-secondary)]'
                                        }
                                    />
                                </span>
                                {isSuggested && (
                                    <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-[1px] text-[var(--bg-turquoise-surf)]">
                                        <span
                                            className="inline-block w-1.5 h-1.5 rounded-full"
                                            style={{ backgroundColor: 'var(--bg-turquoise-surf)' }}
                                            aria-hidden="true"
                                        />
                                        Suggested
                                    </span>
                                )}
                                {!isSuggested && (
                                    <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                                        <InfoTooltip text={mode.detailedDesc} />
                                    </span>
                                )}
                            </div>

                            {/* Label */}
                            <div
                                className={`text-[13px] font-semibold tracking-tight ${
                                    isSelected ? 'text-[var(--bg-turquoise-surf)]' : 'text-[var(--text-primary)]'
                                }`}
                            >
                                {mode.label}
                            </div>

                            {/* One-line action description */}
                            <p className="m-0 text-[11px] text-[var(--text-dim)] leading-[1.4]">
                                {mode.desc}
                            </p>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
